"""
API client for generating Socratic questions and scoring student responses.
Uses the OpenAI-compatible OpenRouter API with exponential-backoff retry logic.
"""

import json
import logging
import time

import openai

from config import (
    SYSTEM_PROMPT_A,
    SYSTEM_PROMPT_B,
    SCORING_PROMPT,
    MODEL,
    TEMPERATURE,
    MAX_TOKENS,
)

logger = logging.getLogger(__name__)

# Retry configuration
_MAX_RETRIES = 2
_RETRY_BASE_DELAY = 1.0   # seconds; doubled on each attempt
_SCORE_MAX_TOKENS = 150   # scoring responses are short JSON objects

_SCORE_KEYS = frozenset({"clarity", "depth", "evidence", "perspectives", "implications"})


class APIClient:
    """Thin wrapper around the OpenRouter chat completions endpoint."""

    def __init__(self, api_key: str) -> None:
        self.client = openai.OpenAI(
            api_key=api_key,
            base_url="https://api.groq.com/openai/v1",
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _call_with_retry(
        self,
        system_prompt: str,
        user_content: str,
        max_tokens: int = MAX_TOKENS,
    ) -> str:
        """
        Call the OpenRouter API with exponential-backoff retry logic.

        Retries are attempted for transient server-side errors (5xx).
        Quota/rate-limit errors (429) fail immediately — retrying in
        seconds cannot help when quota is exhausted.

        Returns:
            The model's reply as a stripped string.

        Raises:
            RuntimeError: On quota exhaustion, with a user-friendly message.
            openai.APIStatusError: On other non-retryable API errors.
        """
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_content},
        ]

        delay = _RETRY_BASE_DELAY
        last_error: Exception | None = None

        for attempt in range(1, _MAX_RETRIES + 1):
            try:
                response = self.client.chat.completions.create(
                    model=MODEL,
                    messages=messages,
                    temperature=TEMPERATURE,
                    max_tokens=max_tokens,
                )
                return response.choices[0].message.content.strip()

            except openai.RateLimitError as exc:
                # Quota exhausted — no point retrying
                raise RuntimeError(
                    "The AI service quota has been exceeded. "
                    "Please generate a new API key at https://console.groq.com/keys "
                    "and update GROQ_API_KEY in .streamlit/secrets.toml."
                ) from exc

            except openai.APIStatusError as exc:
                if exc.status_code and exc.status_code < 500:
                    # Other 4xx errors are not retryable
                    raise
                last_error = exc
                logger.warning(
                    "Server error (attempt %d/%d): %s. Retrying in %.1fs.",
                    attempt, _MAX_RETRIES, exc, delay,
                )

            except (openai.APIConnectionError, openai.APITimeoutError) as exc:
                last_error = exc
                logger.warning(
                    "Network error (attempt %d/%d): %s. Retrying in %.1fs.",
                    attempt, _MAX_RETRIES, exc, delay,
                )

            if attempt < _MAX_RETRIES:
                time.sleep(delay)
                delay *= 2

        raise last_error  # type: ignore[misc]

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def generate_questions(self, student_post: str, system_type: str) -> str:
        """
        Generate Socratic questions for a student's discussion post.

        'A' → Pure Socratic (challenging, no hints)
        'B' → Scaffolded Socratic (guiding, supportive)
        """
        if system_type not in ("A", "B"):
            raise ValueError(f"system_type must be 'A' or 'B', got {system_type!r}.")

        system_prompt = SYSTEM_PROMPT_A if system_type == "A" else SYSTEM_PROMPT_B
        logger.info("Generating questions (system %s, %d words).", system_type, len(student_post.split()))
        questions = self._call_with_retry(system_prompt, student_post)
        logger.info("Received %d characters of questions.", len(questions))
        return questions

    def score_response(self, reply_text: str) -> dict[str, int]:
        """
        Score a student reply using the Paul-Elder critical thinking framework.

        Returns a dict with integer scores (1–4) for clarity, depth,
        evidence, perspectives, and implications.
        """
        logger.info("Scoring reply (%d words).", len(reply_text.split()))
        raw = self._call_with_retry(SCORING_PROMPT, reply_text, max_tokens=_SCORE_MAX_TOKENS)

        # Strip accidental markdown fences
        cleaned = raw.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
        try:
            scores: dict = json.loads(cleaned)
        except json.JSONDecodeError as exc:
            logger.error("Failed to parse scoring JSON: %s\nRaw: %s", exc, raw)
            raise ValueError(f"API returned invalid JSON: {raw!r}") from exc

        missing = _SCORE_KEYS - scores.keys()
        if missing:
            raise ValueError(f"Scoring response missing keys: {missing}. Got: {scores}")

        result: dict[str, int] = {}
        for key in _SCORE_KEYS:
            val = scores[key]
            try:
                int_val = int(val)
            except (TypeError, ValueError):
                logger.warning("Non-numeric score for '%s': %r — defaulting to 1.", key, val)
                int_val = 1
            if not (1 <= int_val <= 4):
                logger.warning("Score '%s' out of range (%d) — clamping.", key, int_val)
                int_val = max(1, min(4, int_val))
            result[key] = int_val

        logger.info("Scores: %s  total=%d", result, sum(result.values()))
        return result
