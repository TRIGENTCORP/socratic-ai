"""
PostgreSQL database layer for the Socratic AI study platform.
All operations use context managers to ensure connections are properly closed.
Connection string is read from st.secrets["DATABASE_URL"] with fallback to
the DATABASE_URL environment variable.
"""

import os
import logging
from contextlib import contextmanager
from datetime import datetime, timezone

import psycopg2
from psycopg2.extras import RealDictCursor

try:
    import streamlit as st
    _DATABASE_URL = st.secrets["DATABASE_URL"]
except Exception:
    _DATABASE_URL = os.environ["DATABASE_URL"]

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@contextmanager
def get_connection():
    """Context manager that yields a database connection and handles cleanup."""
    conn = psycopg2.connect(_DATABASE_URL, cursor_factory=RealDictCursor)
    try:
        yield conn
        conn.commit()
    except psycopg2.Error as e:
        conn.rollback()
        logger.error("Database error: %s", e)
        raise
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Schema
# ---------------------------------------------------------------------------

def init_db():
    """Create all tables if they do not already exist."""
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS students (
                student_id        TEXT PRIMARY KEY,
                system_assignment TEXT NOT NULL CHECK(system_assignment IN ('A', 'B')),
                enrollment_date   TEXT NOT NULL,
                year_of_study     TEXT,
                programme         TEXT
            )
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS posts (
                post_id     SERIAL PRIMARY KEY,
                student_id  TEXT NOT NULL REFERENCES students(student_id),
                week_number INTEGER NOT NULL,
                topic       TEXT NOT NULL,
                post_text   TEXT NOT NULL,
                word_count  INTEGER NOT NULL,
                timestamp   TEXT NOT NULL
            )
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS ai_responses (
                response_id       SERIAL PRIMARY KEY,
                post_id           INTEGER NOT NULL REFERENCES posts(post_id),
                ai_questions_text TEXT NOT NULL,
                timestamp         TEXT NOT NULL
            )
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS replies (
                reply_id    SERIAL PRIMARY KEY,
                response_id INTEGER NOT NULL REFERENCES ai_responses(response_id),
                student_id  TEXT NOT NULL REFERENCES students(student_id),
                reply_text  TEXT NOT NULL,
                word_count  INTEGER NOT NULL,
                timestamp   TEXT NOT NULL
            )
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS ct_scores (
                score_id           SERIAL PRIMARY KEY,
                reply_id           INTEGER NOT NULL REFERENCES replies(reply_id),
                clarity_score      INTEGER NOT NULL,
                depth_score        INTEGER NOT NULL,
                evidence_score     INTEGER NOT NULL,
                perspectives_score INTEGER NOT NULL,
                implications_score INTEGER NOT NULL,
                total_score        INTEGER NOT NULL,
                timestamp          TEXT NOT NULL
            )
        """)
    logger.info("Database initialised.")


# ---------------------------------------------------------------------------
# Write helpers
# ---------------------------------------------------------------------------

def _now() -> str:
    """Return the current UTC time as an ISO-8601 string."""
    return datetime.now(timezone.utc).isoformat()


def add_student(student_id: str, system: str, date: str,
                year_of_study: str = None, programme: str = None) -> None:
    """
    Insert a new student record.

    Args:
        student_id:    Unique identifier for the student.
        system:        Condition assignment – 'A' (control) or 'B' (treatment).
        date:          Enrollment date string (ISO-8601 recommended).
        year_of_study: Optional year/level of study.
        programme:     Optional degree programme name.

    Raises:
        psycopg2.IntegrityError: If student_id already exists or system is invalid.
    """
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO students (student_id, system_assignment, enrollment_date,
                                  year_of_study, programme)
            VALUES (%s, %s, %s, %s, %s)
            """,
            (student_id, system, date, year_of_study, programme),
        )
    logger.info("Added student '%s' (system %s).", student_id, system)


def add_post(student_id: str, week: int, topic: str, text: str) -> int:
    """
    Save a student's weekly discussion post.

    Args:
        student_id: The posting student's ID.
        week:       Week number of the study.
        topic:      Discussion topic title.
        text:       Full post body.

    Returns:
        The auto-assigned post_id for the new record.
    """
    word_count = len(text.split())
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO posts (student_id, week_number, topic, post_text,
                               word_count, timestamp)
            VALUES (%s, %s, %s, %s, %s, %s)
            RETURNING post_id
            """,
            (student_id, week, topic, text, word_count, _now()),
        )
        post_id = cur.fetchone()["post_id"]
    logger.info("Added post %d for student '%s' (week %d).", post_id, student_id, week)
    return post_id


def add_ai_response(post_id: int, questions: str) -> int:
    """
    Save the AI-generated Socratic questions for a post.

    Args:
        post_id:   The post this response belongs to.
        questions: The full text of the AI-generated questions.

    Returns:
        The auto-assigned response_id for the new record.
    """
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO ai_responses (post_id, ai_questions_text, timestamp)
            VALUES (%s, %s, %s)
            RETURNING response_id
            """,
            (post_id, questions, _now()),
        )
        response_id = cur.fetchone()["response_id"]
    logger.info("Added AI response %d for post %d.", response_id, post_id)
    return response_id


def add_reply(response_id: int, student_id: str, text: str) -> int:
    """
    Save a student's reply to AI-generated questions.

    Args:
        response_id: The AI response being replied to.
        student_id:  The replying student's ID.
        text:        Full reply body.

    Returns:
        The auto-assigned reply_id for the new record.
    """
    word_count = len(text.split())
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO replies (response_id, student_id, reply_text,
                                 word_count, timestamp)
            VALUES (%s, %s, %s, %s, %s)
            RETURNING reply_id
            """,
            (response_id, student_id, text, word_count, _now()),
        )
        reply_id = cur.fetchone()["reply_id"]
    logger.info("Added reply %d for response %d.", reply_id, response_id)
    return reply_id


def save_scores(reply_id: int, scores_dict: dict) -> int:
    """
    Save critical-thinking scores for a student reply.

    Expected keys in scores_dict:
        clarity_score, depth_score, evidence_score,
        perspectives_score, implications_score.
    total_score is computed automatically as the sum of the five dimensions.

    Args:
        reply_id:    The reply being scored.
        scores_dict: Dimension scores (see above).

    Returns:
        The auto-assigned score_id for the new record.

    Raises:
        KeyError: If a required score key is missing from scores_dict.
    """
    required = ("clarity_score", "depth_score", "evidence_score",
                 "perspectives_score", "implications_score")
    missing = [k for k in required if k not in scores_dict]
    if missing:
        raise KeyError(f"Missing score keys: {missing}")

    total = sum(scores_dict[k] for k in required)

    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO ct_scores (reply_id, clarity_score, depth_score,
                                   evidence_score, perspectives_score,
                                   implications_score, total_score, timestamp)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING score_id
            """,
            (
                reply_id,
                scores_dict["clarity_score"],
                scores_dict["depth_score"],
                scores_dict["evidence_score"],
                scores_dict["perspectives_score"],
                scores_dict["implications_score"],
                total,
                _now(),
            ),
        )
        score_id = cur.fetchone()["score_id"]
    logger.info("Saved scores (id %d) for reply %d. Total: %d.", score_id, reply_id, total)
    return score_id


# ---------------------------------------------------------------------------
# Read helpers
# ---------------------------------------------------------------------------

def get_student(student_id: str) -> dict | None:
    """
    Fetch a single student record.

    Args:
        student_id: The student to look up.

    Returns:
        A dict with student fields, or None if not found.
    """
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute(
            "SELECT * FROM students WHERE student_id = %s", (student_id,)
        )
        row = cur.fetchone()
    return dict(row) if row else None


def get_conversation(student_id: str, week: int) -> list[dict]:
    """
    Return the full conversation thread for a student in a given week.

    Each element represents one post and contains nested ai_response
    and reply lists if they exist.

    Args:
        student_id: The student whose conversation to retrieve.
        week:       The week number to retrieve.

    Returns:
        A list of dicts, each with keys:
            post        – post record
            ai_response – ai_responses record (or None)
            reply       – replies record (or None)
            scores      – ct_scores record (or None)
    """
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT
                p.post_id, p.week_number, p.topic, p.post_text,
                p.word_count        AS post_word_count,
                p.timestamp         AS post_timestamp,

                ar.response_id, ar.ai_questions_text, ar.timestamp AS ai_timestamp,

                r.reply_id, r.reply_text,
                r.word_count        AS reply_word_count,
                r.timestamp         AS reply_timestamp,

                ct.score_id, ct.clarity_score, ct.depth_score,
                ct.evidence_score, ct.perspectives_score,
                ct.implications_score, ct.total_score,
                ct.timestamp        AS score_timestamp
            FROM posts p
            LEFT JOIN ai_responses ar ON ar.post_id = p.post_id
            LEFT JOIN replies r       ON r.response_id = ar.response_id
            LEFT JOIN ct_scores ct    ON ct.reply_id = r.reply_id
            WHERE p.student_id = %s AND p.week_number = %s
            ORDER BY p.post_id
            """,
            (student_id, week),
        )
        rows = cur.fetchall()

    return [dict(row) for row in rows]


def get_post_for_week(student_id: str, week: int) -> dict | None:
    """
    Return the student's existing post for a given week, or None.

    Used to prevent duplicate submissions and guard the submit form.
    """
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute(
            "SELECT * FROM posts WHERE student_id = %s AND week_number = %s LIMIT 1",
            (student_id, week),
        )
        row = cur.fetchone()
    return dict(row) if row else None


def get_recent_posts(week: int, limit: int = 10) -> list[dict]:
    """
    Return the most recent posts across all students for a given week.

    Args:
        week:  The week number to filter by.
        limit: Maximum number of posts to return (default 10).

    Returns:
        A list of post dicts ordered by timestamp descending.
    """
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT p.*, s.system_assignment, s.programme
            FROM posts p
            JOIN students s ON s.student_id = p.student_id
            WHERE p.week_number = %s
            ORDER BY p.timestamp DESC
            LIMIT %s
            """,
            (week, limit),
        )
        rows = cur.fetchall()

    return [dict(row) for row in rows]
