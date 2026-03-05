"""
Main entry point for the Socratic Learning Forum Streamlit application.
"""

import streamlit as st
from dateutil.relativedelta import relativedelta
from datetime import datetime, timezone

import database
import config

# ---------------------------------------------------------------------------
# Page configuration
# ---------------------------------------------------------------------------

st.set_page_config(
    page_title="Socratic Learning Forum",
    layout="wide",
)

# ---------------------------------------------------------------------------
# Session state initialisation
# ---------------------------------------------------------------------------

defaults = {
    "logged_in": False,
    "student_id": None,
    "system_type": None,
    "current_week": None,
}
for key, value in defaults.items():
    if key not in st.session_state:
        st.session_state[key] = value

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _calculate_week(enrollment_date_str: str) -> int:
    """
    Return the study week number (1–4) based on enrollment date.
    Returns 4 if the student is past the final week.
    """
    enrolled = datetime.fromisoformat(enrollment_date_str).replace(tzinfo=timezone.utc)
    now = datetime.now(timezone.utc)
    weeks_elapsed = (now - enrolled).days // 7 + 1
    return max(1, min(4, weeks_elapsed))


def _do_login(student_id: str) -> None:
    """Validate the student ID and populate session state."""
    if not student_id.strip():
        st.error("Please enter a student ID.")
        return

    student = database.get_student(student_id.strip())
    if student is None:
        st.error(f"Student ID '{student_id}' not found. Please check your ID or contact your administrator.")
        return

    st.session_state.logged_in = True
    st.session_state.student_id = student["student_id"]
    st.session_state.system_type = student["system_assignment"]
    st.session_state.current_week = _calculate_week(student["enrollment_date"])


def _do_logout() -> None:
    """Clear all session state and return to the login screen."""
    for key in defaults:
        st.session_state[key] = defaults[key]
    st.rerun()


# ---------------------------------------------------------------------------
# Database bootstrap
# ---------------------------------------------------------------------------

database.init_db()

# ---------------------------------------------------------------------------
# Login screen
# ---------------------------------------------------------------------------

if not st.session_state.logged_in:
    col_left, col_centre, col_right = st.columns([1, 2, 1])
    with col_centre:
        st.title("Socratic Learning Forum")
        st.markdown("---")
        st.subheader("Sign in")

        student_id_input = st.text_input(
            "Student ID",
            placeholder="e.g. S12345",
            label_visibility="visible",
        )

        if st.button("Log in", use_container_width=True, type="primary"):
            _do_login(student_id_input)
            if st.session_state.logged_in:
                st.rerun()

    st.stop()

# ---------------------------------------------------------------------------
# Sidebar (shown only when logged in)
# ---------------------------------------------------------------------------

with st.sidebar:
    st.markdown(f"### Welcome, {st.session_state.student_id}")
    st.markdown("---")

    current_week = st.session_state.current_week
    weeks_completed = current_week - 1

    st.metric("Current week", f"Week {current_week} of 4")
    st.progress(weeks_completed / 4, text=f"{weeks_completed}/4 weeks completed")

    st.markdown("---")
    if st.button("Log out", use_container_width=True):
        _do_logout()

# ---------------------------------------------------------------------------
# Main page (home / navigation hub)
# ---------------------------------------------------------------------------

st.title("Welcome to the Socratic Learning Forum")
st.markdown(
    "Each week you will read a discussion topic, share your initial thoughts, "
    "then engage with AI-generated questions designed to deepen your reasoning."
)
st.markdown("---")

topic_preview = config.DISCUSSION_TOPICS.get(current_week, "")
with st.container(border=True):
    st.markdown(f"#### Week {current_week} topic")
    st.write(topic_preview)

st.markdown("---")
st.subheader("Navigate")

nav_left, nav_right = st.columns(2)

with nav_left:
    st.page_link(
        "pages/1_forum.py",
        label="Forum — post this week's response",
        icon="💬",
        use_container_width=True,
    )

with nav_right:
    st.page_link(
        "pages/2_conversation.py",
        label="Conversation — view AI questions & replies",
        icon="🤖",
        use_container_width=True,
    )
