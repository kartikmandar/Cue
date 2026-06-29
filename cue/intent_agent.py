from __future__ import annotations

from cue.actions import WorkflowCategory
from cue.agent_models import IntentResult, NormalizedInput
from cue.input_agent import normalize_input


class IntentAgent:
    def classify(self, request: str | NormalizedInput) -> IntentResult:
        normalized = normalize_input(request)
        text = normalized.text.casefold()

        if _contains_any(text, _SENSITIVE_TERMS):
            return _intent(
                normalized,
                WorkflowCategory.SENSITIVE,
                workflow_required=True,
                risk_level="blocked",
                reason="The request touches credentials or other sensitive input.",
                risk_reasons=["password", "credential request is blocked"],
            )

        if "terminal" in text and _contains_any(text, _CODING_TERMS):
            return _intent(
                normalized,
                WorkflowCategory.CODING,
                workflow_required=True,
                risk_level="medium",
                reason="The request asks for a terminal or coding workflow.",
                risk_reasons=["terminal/coding workflows need approval"],
            )

        if "terminal" in text:
            return _intent(
                normalized,
                WorkflowCategory.TERMINAL,
                workflow_required=True,
                risk_level="medium",
                reason="The request asks for a terminal workflow.",
                risk_reasons=["terminal workflows need approval"],
            )

        if _is_app_launch_only(text):
            return _intent(
                normalized,
                WorkflowCategory.APP_LAUNCH,
                workflow_required=True,
                risk_level="low",
                reason="The request asks to open or activate an app.",
            )

        if "pdf" in text:
            return _intent(
                normalized,
                WorkflowCategory.PDF,
                workflow_required=_requires_action(text),
                risk_level="low",
                reason="The request refers to a PDF workflow.",
            )

        if _contains_any(text, _BROWSER_TERMS):
            return _intent(
                normalized,
                WorkflowCategory.BROWSER,
                workflow_required=_requires_action(text),
                risk_level="low",
                reason="The request refers to a browser workflow.",
            )

        if _contains_any(text, _DOCUMENT_TERMS):
            return _intent(
                normalized,
                WorkflowCategory.DOCUMENT,
                workflow_required=True,
                risk_level="low",
                reason="The request asks for a local document workflow.",
                risk_reasons=["document editing changes state"],
            )

        if _contains_any(text, _APP_LAUNCH_TERMS):
            return _intent(
                normalized,
                WorkflowCategory.APP_LAUNCH,
                workflow_required=True,
                risk_level="low",
                reason="The request asks to open or activate an app.",
            )

        if _is_read_only_answer_request(text):
            return _intent(
                normalized,
                WorkflowCategory.ANSWER,
                workflow_required=False,
                risk_level="none",
                reason="The user asked for a read-only answer.",
            )

        return _intent(
            normalized,
            WorkflowCategory.DESKTOP,
            workflow_required=True,
            risk_level="low",
            reason="The request appears to require desktop workflow planning.",
        )


def classify_intent(request: str | NormalizedInput) -> IntentResult:
    return IntentAgent().classify(request)


def _intent(
    normalized: NormalizedInput,
    category: WorkflowCategory,
    *,
    workflow_required: bool,
    risk_level: str,
    reason: str,
    risk_reasons: list[str] | None = None,
) -> IntentResult:
    return IntentResult(
        normalized_input=normalized,
        intent=category.value,
        workflow_required=workflow_required,
        workflow_category=category,
        risk_level=risk_level,
        reason=reason,
        risk_reasons=risk_reasons or [],
    )


def _contains_any(text: str, terms: tuple[str, ...]) -> bool:
    return any(term in text for term in terms)


def _requires_action(text: str) -> bool:
    return _contains_any(text, _APP_LAUNCH_TERMS + _STATE_CHANGE_TERMS)


def _is_app_launch_only(text: str) -> bool:
    return (
        _contains_any(text, _APP_LAUNCH_TERMS)
        and _contains_any(text, _APP_LAUNCH_TARGET_TERMS)
        and not _contains_any(text, _STATE_CHANGE_TERMS)
    )


def _is_read_only_answer_request(text: str) -> bool:
    return _contains_any(text, _ANSWER_TERMS) and not _contains_any(
        text,
        _STATE_CHANGE_TERMS,
    )


_ANSWER_TERMS = (
    "what is on my screen",
    "what's on my screen",
    "what is happening on my screen",
    "what's happening on my screen",
    "what is happening on the screen",
    "what's happening on the screen",
    "happening on the screen",
    "what app am i in",
    "where is my focus",
    "summarize",
    "read visible",
    "tell me what is on",
)
_APP_LAUNCH_TERMS = ("open ", "launch ", "activate ", "switch to ", "focus ")
_STATE_CHANGE_TERMS = ("write", "type", "fill", "click", "set", "press", "add")
_APP_LAUNCH_TARGET_TERMS = (
    " app",
    "textedit",
    "text edit",
    "notes",
    "finder",
    "safari",
    "chrome",
    "google chrome",
    "terminal",
    "calendar",
    "reminders",
    "mail",
    "messages",
    "contacts",
    "facetime",
    "maps",
    "photos",
    "music",
    "calculator",
    "dictionary",
    "stickies",
    "voice memos",
    "quicktime player",
)
_DOCUMENT_TERMS = (
    "textedit",
    "document",
    "write",
    "title",
    "heading",
    "note",
)
_BROWSER_TERMS = ("browser", "safari", "chrome", "web page", "website", "url")
_CODING_TERMS = ("claude code", "code", "repo", "project", "developer")
_SENSITIVE_TERMS = (
    "password",
    "passcode",
    "credential",
    "mfa",
    "one-time code",
    "otp",
    "security code",
)
