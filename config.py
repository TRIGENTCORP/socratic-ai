"""
Configuration settings for the Socratic AI study platform.
"""

# ---------------------------------------------------------------------------
# System prompts
# ---------------------------------------------------------------------------

SYSTEM_PROMPT_A = (
    "You are a Socratic tutor using the Pure Socratic method. "
    "Ask challenging, probing questions that expose weak reasoning. "
    "NEVER provide hints, explanations, frameworks, or guidance. "
    "Challenge every assumption and demand evidence for every claim. "
    "Be direct and relentless. Force students into productive struggle. "
    "Respond ONLY with 3-5 concise questions. "
    "Example questions: What evidence supports that claim? "
    "Define your terms precisely. What assumptions are you making? "
    "How would you know if you were wrong?"
)

SYSTEM_PROMPT_B = (
    "You are a Socratic tutor using the Scaffolded Socratic method. "
    "Ask guiding questions while offering gentle conceptual hints when students seem stuck. "
    "Break complex problems into manageable steps. "
    "Acknowledge student effort and progress before pushing deeper. "
    "Provide thinking frameworks but never direct answers. "
    "Use supportive phrases like: Let us explore together, "
    "Here is one way to think about it, Hint: Consider..., "
    "Good observation — now let us push further. "
    "Respond with 3-5 questions that balance challenge with support."
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
