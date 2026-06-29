from __future__ import annotations

from typing import Protocol

from cue.agent_models import NarrationResult, VerificationResult, WorkflowPlan, WorkflowStep
from cue.context import DesktopObservation


class PolicyBlockLike(Protocol):
    reason: str
    risk_reasons: list[str]
    redaction_required: bool


class Narrator:
    def describe_screen(self, observation: DesktopObservation) -> NarrationResult:
        app = observation.active_app or "unknown app"
        window = observation.active_window or "unknown window"
        focus = _focus_text(observation)
        cursor = _cursor_text(observation)
        text = f"Current screen: {app}, window {window}. Focus: {focus}. Cursor: {cursor}."
        return NarrationResult(summary=text, speakable_text=text)

    def describe_plan(self, plan: WorkflowPlan) -> NarrationResult:
        count = len(plan.steps)
        step_word = "step" if count == 1 else "steps"
        titles = "; ".join(
            f"{index}. {step.title}" for index, step in enumerate(plan.steps, start=1)
        )
        if not titles:
            titles = "No desktop action is needed."
        text = (
            f"Workflow plan: {count} {step_word}. {titles}. "
            f"Approval: {plan.approval_tier.value}. Expected: {plan.expected_outcome}"
        )
        return NarrationResult(
            summary=text,
            speakable_text=text,
            redaction_applied=plan.redaction_applied,
        )

    def confirmation_prompt(
        self,
        plan: WorkflowPlan,
        step: WorkflowStep | None = None,
    ) -> NarrationResult:
        if step is None:
            text = plan.confirmation_prompt
        else:
            text = (
                f"Approve next step: {step.title}. "
                f"{step.action.reason} Expected: {step.expected_outcome}"
            )
        return NarrationResult(
            summary=text,
            speakable_text=text,
            redaction_applied=plan.redaction_applied,
        )

    def policy_block(self, decision: PolicyBlockLike) -> NarrationResult:
        risks = _join_or_none(decision.risk_reasons)
        text = f"Blocked: {decision.reason}"
        if risks:
            text = f"{text} Risks: {risks}."
        return NarrationResult(
            summary=text,
            speakable_text=text,
            redaction_applied=decision.redaction_required,
        )

    def verification(self, result: VerificationResult) -> NarrationResult:
        label = {
            "passed": "Verification passed",
            "failed": "Verification failed",
            "unknown": "Verification unknown",
        }[result.status]
        parts = [f"{label}: {result.reason}"]
        if result.expected:
            parts.append(f"Expected: {result.expected}")
        if result.actual:
            parts.append(f"Actual: {result.actual}")
        if result.next_recommendation:
            parts.append(f"Next: {result.next_recommendation}")
        text = ". ".join(parts) + "."
        return NarrationResult(summary=text, speakable_text=text)

    def next_step(self, step: WorkflowStep) -> NarrationResult:
        text = (
            f"Next step: {step.title}. {step.action.reason} "
            f"Expected: {step.expected_outcome}"
        )
        return NarrationResult(summary=text, speakable_text=text)


def _focus_text(observation: DesktopObservation) -> str:
    focus = observation.focused_element
    if focus.status != "known":
        return focus.reason or "unknown"

    parts = [focus.role, focus.title]
    if focus.value:
        parts.append(f"value {focus.value}")
    return ", ".join(part for part in parts if part) or "known focus"


def _cursor_text(observation: DesktopObservation) -> str:
    cursor = observation.cursor_position
    if cursor.status != "known":
        return cursor.reason or "unknown"
    return f"{cursor.x}, {cursor.y}"


def _join_or_none(values: list[str]) -> str | None:
    clean = [value for value in values if value]
    return "; ".join(clean) if clean else None
