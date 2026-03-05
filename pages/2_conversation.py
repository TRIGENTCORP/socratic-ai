"""
Conversation page — displays a student's full dialogue with the AI tutor
and handles reply submission, scoring, and follow-up question generation.
"""

import html
import os
import pathlib
import sys

import streamlit as st

import database
import config
from utils.api_client import APIClient

# ---------------------------------------------------------------------------
# Page config (must be first Streamlit call)
# ---------------------------------------------------------------------------

st.set_page_config(page_title="Conversation — Socratic Learning", layout="wide")

# ---------------------------------------------------------------------------
# Login guard
# ---------------------------------------------------------------------------

if not st.session_state.get("logged_in"):
    st.switch_page("app.py")
    st.stop()

student_id: str = st.session_state.student_id
system_type: str = st.session_state.system_type
current_week: int = st.session_state.current_week

MAX_EXCHANGES = 3   # AI question + student reply pairs allowed per week
WORD_MIN = 50
WORD_MAX = 500

# ---------------------------------------------------------------------------
# API client
# ---------------------------------------------------------------------------

def _load_api_key() -> str:
    """
    Load the OpenAI API key with three-tier fallback:
      1. st.secrets (works when Streamlit server started after secrets.toml existed)
      2. GROQ_API_KEY environment variable
      3. Direct read of .streamlit/secrets.toml (works even if Streamlit missed it)
    """
    # Tier 1 — Streamlit secrets
    try:
        key = st.secrets.get("GROQ_API_KEY", "")
        if key:
            return key
    except Exception:
        pass

    # Tier 2 — environment variable
    key = os.environ.get("GROQ_API_KEY", "")
    if key:
        return key

    # Tier 3 — read secrets.toml directly (handles server started before file existed)
    try:
        toml_path = pathlib.Path(__file__).parent.parent / ".streamlit" / "secrets.toml"
        if sys.version_info >= (3, 11):
            import tomllib
            with open(toml_path, "rb") as f:
                data = tomllib.load(f)
        else:
            import tomli
            with open(toml_path, "rb") as f:
                data = tomli.load(f)
        return data.get("GROQ_API_KEY", "")
    except Exception:
        return ""


@st.cache_resource
def get_api_client() -> APIClient:
    api_key = _load_api_key()
    if not api_key:
        st.error("API key not configured. Set GROQ_API_KEY in .streamlit/secrets.toml.")
        st.stop()
    return APIClient(api_key=api_key)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _fmt_ts(ts: str) -> str:
    """Format an ISO-8601 UTC timestamp for display."""
    try:
        from datetime import datetime, timezone
        dt = datetime.fromisoformat(ts).astimezone(timezone.utc)
        return dt.strftime("%d %b %Y  %H:%M UTC")
    except (ValueError, TypeError):
        return ts or ""


def _score_band(total: int) -> str:
    if total >= 16:
        return "Excellent"
    if total >= 12:
        return "Good"
    if total >= 8:
        return "Developing"
    return "Beginning"


def _parse_conversation(rows: list[dict]) -> tuple[dict | None, list[dict]]:
    """
    Convert flat JOIN rows from get_conversation() into a structured thread.

    Returns:
        post:      Dict with post fields, or None if there is no post.
        exchanges: List of exchange dicts sorted by response_id, each with:
                     response_id, ai_questions_text, ai_timestamp,
                     reply (dict with reply fields + nested scores, or None)
    """
    if not rows:
        return None, []

    first = rows[0]
    post = {
        "post_id":    first["post_id"],
        "post_text":  first["post_text"],
        "word_count": first["post_word_count"],
        "timestamp":  first["post_timestamp"],
    }

    exchanges_by_id: dict[int, dict] = {}
    for row in rows:
        rid = row["response_id"]
        if rid is None:
            continue
        if rid not in exchanges_by_id:
            exchanges_by_id[rid] = {
                "response_id":      rid,
                "ai_questions_text": row["ai_questions_text"],
                "ai_timestamp":     row["ai_timestamp"],
                "reply":            None,
            }
        if row["reply_id"] is not None:
            exchanges_by_id[rid]["reply"] = {
                "reply_id":   row["reply_id"],
                "reply_text": row["reply_text"],
                "word_count": row["reply_word_count"],
                "timestamp":  row["reply_timestamp"],
                "scores": {
                    "clarity_score":      row["clarity_score"],
                    "depth_score":        row["depth_score"],
                    "evidence_score":     row["evidence_score"],
                    "perspectives_score": row["perspectives_score"],
                    "implications_score": row["implications_score"],
                    "total_score":        row["total_score"],
                } if row["score_id"] is not None else None,
            }

    exchanges = sorted(exchanges_by_id.values(), key=lambda x: x["response_id"])
    return post, exchanges


# ---------------------------------------------------------------------------
# Bubble renderers
# ---------------------------------------------------------------------------

_BUBBLE_STUDENT = (
    "background:#dbeafe; border-radius:12px; padding:14px 18px; margin-bottom:6px;"
    "border-left:4px solid #3b82f6; color:#1e293b;"
)
_BUBBLE_AI = (
    "background:#e5e7eb; border-radius:12px; padding:14px 18px; margin-bottom:6px;"
    "border-left:4px solid #6b7280; color:#1e293b;"
)
_META = "margin:0 0 8px 0; font-size:0.78rem; color:{color};"
_BODY = "margin:0; white-space:pre-wrap; line-height:1.6; color:#1e293b;"


def _render_student_bubble(
    text: str,
    ts: str,
    label: str = "You",
    wc: int | None = None,
    scores: dict | None = None,
) -> None:
    meta_parts = [f"<strong>{html.escape(label)}</strong>", _fmt_ts(ts)]
    if wc:
        meta_parts.append(f"{wc} words")
    meta = " &nbsp;·&nbsp; ".join(meta_parts)

    st.markdown(
        f'<div style="{_BUBBLE_STUDENT}">'
        f'<p style="{_META.format(color="#1d4ed8")}">{meta}</p>'
        f'<p style="{_BODY}">{html.escape(text)}</p>'
        "</div>",
        unsafe_allow_html=True,
    )

    if scores:
        with st.expander("Critical thinking scores", expanded=False):
            dims = ["clarity", "depth", "evidence", "perspectives", "implications"]
            cols = st.columns(len(dims))
            for col, dim in zip(cols, dims):
                col.metric(dim.capitalize(), f"{scores[dim + '_score']}/4")
            total = scores["total_score"]
            st.caption(f"Total: **{total}/20** — {_score_band(total)}")


def _render_ai_bubble(text: str, ts: str, exchange_num: int) -> None:
    meta = f"<strong>AI Tutor</strong> &nbsp;·&nbsp; {_fmt_ts(ts)} &nbsp;·&nbsp; Exchange {exchange_num}"

    st.markdown(
        f'<div style="{_BUBBLE_AI}">'
        f'<p style="{_META.format(color="#1f2937")}">{meta}</p>'
        f'<p style="{_BODY}">{html.escape(text)}</p>'
        "</div>",
        unsafe_allow_html=True,
    )


# ---------------------------------------------------------------------------
# Sidebar
# ---------------------------------------------------------------------------

with st.sidebar:
    st.markdown(f"### {student_id}")
    st.caption(f"Week {current_week} of 4  •  System {system_type}")
    st.markdown("---")
    if st.button("Log out", use_container_width=True):
        for key in ("logged_in", "student_id", "system_type", "current_week"):
            st.session_state[key] = None if key != "logged_in" else False
        st.switch_page("app.py")

# ---------------------------------------------------------------------------
# Page header
# ---------------------------------------------------------------------------

st.title("My Conversation")
st.caption(f"Week {current_week}")

topic_text = config.DISCUSSION_TOPICS.get(current_week, "")
with st.container(border=True):
    st.markdown(f"#### Week {current_week} Topic")
    st.write(topic_text)

st.markdown("---")

# ---------------------------------------------------------------------------
# Load and parse conversation
# ---------------------------------------------------------------------------

rows = database.get_conversation(student_id=student_id, week=current_week)
post, exchanges = _parse_conversation(rows)

# ---------------------------------------------------------------------------
# Empty state
# ---------------------------------------------------------------------------

if post is None:
    st.info("Submit a post in the Forum first to start your conversation!")
    st.page_link("pages/1_forum.py", label="Go to Forum", icon="💬")
    st.stop()

# ---------------------------------------------------------------------------
# Conversation thread
# ---------------------------------------------------------------------------

_render_student_bubble(
    text=post["post_text"],
    ts=post["timestamp"],
    label="Your post",
    wc=post["word_count"],
)

for i, ex in enumerate(exchanges, start=1):
    st.markdown("<div style='margin-top:14px;'></div>", unsafe_allow_html=True)
    _render_ai_bubble(ex["ai_questions_text"], ex["ai_timestamp"], exchange_num=i)

    if ex["reply"]:
        st.markdown("<div style='margin-top:8px;'></div>", unsafe_allow_html=True)
        _render_student_bubble(
            text=ex["reply"]["reply_text"],
            ts=ex["reply"]["timestamp"],
            wc=ex["reply"]["word_count"],
            scores=ex["reply"]["scores"],
        )

st.markdown("---")

# ---------------------------------------------------------------------------
# Reply section
# ---------------------------------------------------------------------------

num_complete = sum(1 for ex in exchanges if ex["reply"] is not None)
last_exchange = exchanges[-1] if exchanges else None
has_unanswered = last_exchange is not None and last_exchange["reply"] is None
limit_reached = num_complete >= MAX_EXCHANGES

if limit_reached:
    st.success(
        f"You have completed all {MAX_EXCHANGES} exchanges for Week {current_week}. "
        "Great work — your responses have been saved and scored."
    )

elif has_unanswered:
    is_final_reply = (num_complete + 1) >= MAX_EXCHANGES

    st.subheader("Your reply")
    st.caption(
        f"Exchange {num_complete + 1} of {MAX_EXCHANGES}"
        + (" (final)" if is_final_reply else "")
        + f"  •  {WORD_MIN}–{WORD_MAX} words"
    )

    if "reply_area_key" not in st.session_state:
        st.session_state.reply_area_key = 0

    reply_text: str = st.text_area(
        label="Your reply",
        placeholder="Respond to the questions above. Reason carefully and support your claims…",
        height=220,
        key=f"reply_input_{st.session_state.reply_area_key}",
        label_visibility="collapsed",
    )

    wc = len(reply_text.split()) if reply_text.strip() else 0

    count_col, char_col = st.columns([1, 3])
    with count_col:
        if wc < WORD_MIN:
            st.caption(f":red[{wc} words] — minimum {WORD_MIN}")
        elif wc > WORD_MAX:
            st.caption(f":red[{wc} words] — maximum {WORD_MAX}")
        else:
            st.caption(f":green[{wc} words] ✓")
    with char_col:
        st.caption(f"{len(reply_text)} characters")

    if st.button(
        "Submit reply",
        disabled=not (WORD_MIN <= wc <= WORD_MAX),
        type="primary",
    ):
        client = get_api_client()
        status = st.empty()

        try:
            with status.container():
                # 1. Score first — before saving the reply so that a scoring
                #    failure leaves the form open with nothing written to the DB.
                scores_dict = None
                with st.spinner("Scoring your response…"):
                    try:
                        raw = client.score_response(reply_text)
                        scores_dict = {f"{k}_score": v for k, v in raw.items()}
                    except Exception as score_exc:
                        st.warning(f"Scoring unavailable this time: {score_exc}")

                # 2. Save the reply to the database
                with st.spinner("Saving your reply…"):
                    reply_id = database.add_reply(
                        response_id=last_exchange["response_id"],
                        student_id=student_id,
                        text=reply_text,
                    )

                # 3. Persist scores if scoring succeeded
                if scores_dict:
                    database.save_scores(reply_id=reply_id, scores_dict=scores_dict)

                # 4. Generate follow-up questions (skipped on the final reply)
                if not is_final_reply:
                    with st.spinner("Generating follow-up questions…"):
                        follow_up = client.generate_questions(
                            student_post=reply_text,
                            system_type=system_type,
                        )
                        database.add_ai_response(
                            post_id=post["post_id"],
                            questions=follow_up,
                        )

        except Exception as exc:
            st.error(f"Something went wrong: {exc}")
            st.stop()

        status.empty()
        st.session_state.reply_area_key += 1
        st.rerun()

else:
    # Post exists with no exchanges — should be transient but handle gracefully.
    st.info("AI questions are being prepared. Refresh the page in a moment.")
