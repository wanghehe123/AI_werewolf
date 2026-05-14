FORBIDDEN_TERMS = [
    "系统提示",
    "system prompt",
    "role_key",
    "LangGraph",
    "JSON",
    "隐藏字段",
]


def is_safe_speech(speech: str) -> bool:
    lowered = speech.lower()
    return not any(term.lower() in lowered for term in FORBIDDEN_TERMS)
