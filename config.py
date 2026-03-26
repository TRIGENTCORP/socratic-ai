"""
Configuration settings for the Socratic AI study platform.
"""

# ---------------------------------------------------------------------------
# System prompts
# ---------------------------------------------------------------------------

SYSTEM_PROMPT_A = (
    "You are a Socratic tutor using the Pure Socratic method. "
    "Read the student's response carefully and briefly acknowledge what they said before asking questions. "
    "Then ask 1-2 focused, probing questions that target the weakest part of their reasoning. "
    "Do not list many questions at once — pick the most important thread and pull on it. "
    "NEVER provide hints, explanations, frameworks, or direct answers. "
    "Keep your tone calm and curious, not aggressive. The goal is to make the student think, not to overwhelm them."
)

SYSTEM_PROMPT_B = (
    "You are a Socratic tutor using the Scaffolded Socratic method. "
    "Start by genuinely engaging with what the student said — acknowledge their point or observation in 1-2 sentences. "
    "Then ask 1-2 guiding questions that help them go one step deeper. "
    "Do not bombard them with multiple questions — choose the most useful one and follow with at most one more. "
    "Offer a gentle hint or reframe only if they seem genuinely stuck. "
    "Keep the tone warm and conversational, like a thoughtful discussion partner, not an examiner."
)

# ---------------------------------------------------------------------------
# Weekly discussion topics
# ---------------------------------------------------------------------------

DISCUSSION_TOPICS = {
    1: (
        "AI and Employment: Many experts claim AI will replace most jobs within the next decade. "
        "Do you agree? What types of work are most vulnerable to automation, and what types are "
        "likely to remain human-dominated? What evidence supports your position?"
    ),
    2: (
        "AI in Education: AI tools like ChatGPT are now widely used by students for assignments. "
        "Should universities ban these tools, embrace them, or take a different approach? "
        "What are the implications for learning and academic integrity?"
    ),
    3: (
        "AI and Privacy: Social media platforms and AI systems collect vast amounts of personal "
        "data to personalize content and advertisements. Is this trade-off (privacy for "
        "convenience) acceptable? At what point does data collection become harmful?"
    ),
    4: (
        "AI Decision-Making: AI systems are increasingly used to make high-stakes decisions: "
        "medical diagnoses, loan approvals, criminal sentencing, hiring. Should humans always "
        "have the final say in these decisions, or are there contexts where AI alone should "
        "decide? What principles should guide this?"
    ),
}

# ---------------------------------------------------------------------------
# Scoring prompt
# ---------------------------------------------------------------------------

SCORING_PROMPT = (
    "Rate this student response on a scale of 1-4 for each dimension. "
    "Return ONLY valid JSON with no markdown:\n"
    "{\n"
    '  "clarity": <1-4>,\n'
    '  "depth": <1-4>,\n'
    '  "evidence": <1-4>,\n'
    '  "perspectives": <1-4>,\n'
    '  "implications": <1-4>\n'
    "}\n\n"
    "1 = minimal critical thinking, 4 = strong critical thinking"
)

# ---------------------------------------------------------------------------
# API settings
# ---------------------------------------------------------------------------

MODEL = "llama-3.3-70b-versatile"
TEMPERATURE = 0.7
MAX_TOKENS = 500
