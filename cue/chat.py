from __future__ import annotations

import re
from uuid import uuid4


CASUAL_TERMS = (
    "hello",
    "hi",
    "hey",
    "how are you",
    "good morning",
    "good afternoon",
    "good evening",
)
HELP_TERMS = (
    "what can you do",
    "help",
    "how do i use",
    "how can i use",
    "what are you",
    "who are you",
)


def conversation_id(existing: str | None = None) -> str:
    value = (existing or "").strip()
    return value or uuid4().hex


def is_conversation_only(text: str) -> bool:
    normalized = text.strip().casefold()
    if not normalized:
        return False
    return _contains_term(normalized, CASUAL_TERMS + HELP_TERMS)


def conversational_reply(text: str) -> str:
    normalized = text.strip().casefold()
    if _contains_term(normalized, HELP_TERMS):
        return (
            "Cue is a voice-first desktop assistant. You can ask naturally, and I "
            "will either answer or prepare a safe desktop action for you to approve. "
            "Say things like, 'what app am I in', 'open TextEdit', or 'cancel'. "
            "You can also type instead whenever voice is not convenient."
        )
    return (
        "I am ready. Cue is designed to start with voice, then fall back to typing "
        "when you want it. Ask me what you want to do on the Mac, and I will answer "
        "or ask before changing anything."
    )


def suggested_replies(text: str) -> list[str]:
    normalized = text.strip().casefold()
    if _contains_term(normalized, HELP_TERMS):
        return [
            "What app am I in?",
            "Open TextEdit",
            "Switch to typing",
        ]
    return [
        "What can you do?",
        "What app am I in?",
        "Open TextEdit",
    ]


def _contains_term(normalized_text: str, terms: tuple[str, ...]) -> bool:
    return any(
        re.search(rf"\b{re.escape(term)}\b", normalized_text) is not None
        for term in terms
    )


def assistant_message_for_session(session: dict) -> str:
    state = str(session.get("state") or "")
    narration = session.get("narration") or {}
    speakable = narration.get("speakable_text") if isinstance(narration, dict) else None
    if state == "blocked":
        return speakable or "I cannot do that because Cue safety policy blocked it."
    if state == "completed":
        return speakable or "I checked that for you."
    confirmation = session.get("confirmation_prompt")
    if confirmation:
        return f"I can do that. {confirmation}"
    return speakable or "I prepared the next step."


def mode_for_session(session: dict) -> str:
    state = str(session.get("state") or "")
    plan = session.get("workflow_plan")
    if state == "blocked":
        return "blocked"
    if state == "completed" and not plan:
        return "conversation"
    if state == "completed":
        return "screen_answer"
    return "action_preview"
