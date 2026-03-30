"""
Forum page — students submit their weekly discussion post and view recent posts.
"""

import os
import sys
import pathlib

import streamlit as st

import database
import config
from utils.api_client import APIClient

# ---------------------------------------------------------------------------
# Login guard
# ---------------------------------------------------------------------------

if not st.session_state.get("logged_in"):
    st.switch_page("app.py")
    st.stop()

student_id: str = st.session_state.student_id
system_type: str = st.session_state.system_type
current_week: int = st.session_state.current_week

# ---------------------------------------------------------------------------
# Page config & session state
# ---------------------------------------------------------------------------

st.set_page_config(page_title="Forum — Socratic Learning", layout="wide")

# Incrementing this key resets the text area widget after a successful submit.
if "post_area_key" not in st.session_state:
    st.session_state.post_area_key = 0

if "submit_success" not in st.session_state:
    st.session_state.submit_success = False

# ---------------------------------------------------------------------------
# API client (initialised once per session)
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
        st.error("API key not configured. Set GROQ_API_KEY in .streamlit/secrets.toml or as an environment variable.")
        st.stop()
    return APIClient(api_key=api_key)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

WORD_MIN = 50
WORD_MAX = 500


def _word_count(text: str) -> int:
    return len(text.split()) if text.strip() else 0


def _anonymise(sid: str) -> str:
    """Show only the last 3 characters of a student ID."""
    return f"Student_...{sid[-3:]}" if len(sid) > 3 else "Student_???"


def _short_timestamp(ts: str) -> str:
    """Format an ISO-8601 timestamp as a readable short string."""
    try:
        from datetime import datetime, timezone
        dt = datetime.fromisoformat(ts).astimezone(timezone.utc)
        return dt.strftime("%d %b %Y  %H:%M UTC")
    except (ValueError, TypeError):
        return ts

# ---------------------------------------------------------------------------
# Sidebar (shared chrome)
# ---------------------------------------------------------------------------

with st.sidebar:
    st.markdown(f"### {student_id}")
    st.caption(f"Week {current_week} of 4  •  System {system_type}")
    st.markdown("---")
    if st.button("Log out", use_container_width=True):
        for key in ("logged_in", "student_id", "system_type", "current_week"):
            st.session_state[key] = None if key != "logged_in" else False
        st.query_params.clear()
        st.switch_page("app.py")

# ---------------------------------------------------------------------------
# Page title
# ---------------------------------------------------------------------------

st.title("Discussion Forum")
st.caption(f"Week {current_week}")

# ---------------------------------------------------------------------------
# Topic display
# ---------------------------------------------------------------------------

topic_text = config.DISCUSSION_TOPICS.get(current_week, "No topic set for this week.")

with st.container(border=True):
    st.markdown(f"#### Week {current_week} Topic")
    st.write(topic_text)

st.markdown("---")

# ---------------------------------------------------------------------------
# Post submission
# ---------------------------------------------------------------------------

existing_post = database.get_post_for_week(student_id, current_week)

if existing_post:
    st.subheader("Your post this week")
    with st.container(border=True):
        st.write(existing_post["post_text"])
        st.caption(
            f"{existing_post['word_count']} words  •  {_short_timestamp(existing_post['timestamp'])}"
        )
    st.info("You have already submitted this week. Head to **Conversation** to engage with your AI questions.")

else:
    st.subheader("Submit your post")

    post_text: str = st.text_area(
        label="Your response",
        placeholder="Write your initial thoughts on this week's topic here…",
        height=250,
        key=f"post_input_{st.session_state.post_area_key}",
        label_visibility="collapsed",
    )

    wc = _word_count(post_text)

    # Live word / character counter
    count_col, hint_col = st.columns([1, 3])
    with count_col:
        if wc < WORD_MIN:
            st.caption(f":red[{wc} words] — minimum {WORD_MIN}")
        elif wc > WORD_MAX:
            st.caption(f":red[{wc} words] — maximum {WORD_MAX}")
        else:
            st.caption(f":green[{wc} words] ✓")
    with hint_col:
        st.caption(f"{len(post_text)} characters  •  {WORD_MIN}–{WORD_MAX} words required")

    submit_disabled = not (WORD_MIN <= wc <= WORD_MAX)

    if st.button(
        "Submit post",
        disabled=submit_disabled,
        type="primary",
        use_container_width=False,
    ):
        client = get_api_client()

        with st.spinner("Generating questions and saving your post…"):
            try:
                # 1. Generate questions first — no DB write yet, so a failed
                #    API call leaves nothing orphaned in the database.
                questions = client.generate_questions(
                    student_post=post_text,
                    system_type=system_type,
                )

                # 2. Persist the post
                post_id = database.add_post(
                    student_id=student_id,
                    week=current_week,
                    topic=topic_text,
                    text=post_text,
                )

                # 3. Persist the AI response
                database.add_ai_response(post_id=post_id, questions=questions)

            except Exception as exc:
                st.error(f"Something went wrong: {exc}")
                st.stop()

        st.session_state.post_area_key += 1
        st.session_state.submit_success = True
        st.rerun()

    if st.session_state.submit_success:
        st.success("Post submitted! Check **My Conversation** to see your AI questions.")
        st.session_state.submit_success = False

st.markdown("---")

# ---------------------------------------------------------------------------
# Recent posts
# ---------------------------------------------------------------------------

st.subheader("Recent posts this week")

recent = database.get_recent_posts(week=current_week, limit=20)

if not recent:
    st.info("No posts yet this week — be the first!")
else:
    for post in recent:
        label = _anonymise(post["student_id"])
        timestamp = _short_timestamp(post["timestamp"])
        preview = post["post_text"][:200].rstrip()
        if len(post["post_text"]) > 200:
            preview += "…"

        with st.container(border=True):
            meta_col, word_col = st.columns([4, 1])
            with meta_col:
                st.markdown(f"**{label}** &nbsp;·&nbsp; {timestamp}")
            with word_col:
                st.caption(f"{post['word_count']} words")
            st.write(preview)
