from __future__ import annotations

from collections.abc import Callable, Mapping
from enum import Enum
from typing import Any, Protocol
from uuid import uuid4

from cue.actions import ActionType, CueAction
from cue.agent_models import (
    NarrationResult,
    PlanReview,
    VerificationResult,
    WorkflowPlan,
    WorkflowSession,
    WorkflowStep,
)
from cue.config import Settings
from cue.context import DesktopObservation
from cue.memory import SessionMemory
from cue.narrator import Narrator
from cue.policy import ApprovalTier
from cue.reviewer import review_plan
from cue.safety import (
    FocusSnapshot,
    SafetyDecision,
    evaluate_step_before_execution,
    evaluate_workflow_plan,
)
from cue.verifier import Verifier


class SessionState(str, Enum):
    IDLE = "idle"
    PREVIEW_READY = "preview_ready"
    AWAITING_WORKFLOW_APPROVAL = "awaiting_workflow_approval"
    AWAITING_STEP_APPROVAL = "awaiting_step_approval"
    AWAITING_REVIEWER_APPROVAL = "awaiting_reviewer_approval"
    EXECUTING_STEP = "executing_step"
    VERIFICATION_FAILED = "verification_failed"
    COMPLETED = "completed"
    BLOCKED = "blocked"
    CANCELLED = "cancelled"
    ERROR = "error"


class PlannerLike(Protocol):
    def __call__(
        self,
        request: str,
        observation: DesktopObservation | Mapping[str, Any],
    ) -> WorkflowPlan: ...


class ReviewerLike(Protocol):
    def __call__(self, plan: WorkflowPlan) -> PlanReview: ...


class ExecutorLike(Protocol):
    def __call__(self, action: CueAction) -> Any: ...


class VerifierLike(Protocol):
    def verify_step(self, step: WorkflowStep) -> VerificationResult: ...


class CueSessionOrchestrator:
    def __init__(
        self,
        *,
        settings: Settings,
        observer: Callable[[], DesktopObservation | Mapping[str, Any]],
        planner: PlannerLike,
        reviewer: ReviewerLike | None = None,
        executor: ExecutorLike | None = None,
        verifier: VerifierLike | None = None,
        narrator: Narrator | None = None,
        memory: SessionMemory | None = None,
        session_id: str | None = None,
    ) -> None:
        self.settings = settings
        self.session_id = session_id or uuid4().hex
        self._observer = observer
        self._planner = planner
        self._reviewer = reviewer or review_plan
        self._executor = executor or self._unsupported_executor
        self._verifier = verifier or Verifier(observer)
        self._narrator = narrator or Narrator()
        self._memory = memory

        self._state = SessionState.IDLE
        self._plan: WorkflowPlan | None = None
        self._preview_decision: SafetyDecision | None = None
        self._preview_observation: DesktopObservation | Mapping[str, Any] | None = None
        self._preview_snapshot: FocusSnapshot | None = None
        self._last_observation: DesktopObservation | Mapping[str, Any] | None = None
        self._workflow_approved = False
        self._reviewer_requested = False
        self._reviewer_approved = False
        self._current_step_index = 0
        self._verified_steps: list[str] = []
        self._last_verification: VerificationResult | None = None
        self._narration: NarrationResult | None = None

    def preview(self, request: str) -> WorkflowSession:
        try:
            observation = self._observe()
            self._preview_observation = observation
            self._preview_snapshot = _focus_snapshot(observation)
            plan = self._planner(request, observation)
            self._plan = plan
            self._workflow_approved = False
            self._reviewer_requested = False
            self._reviewer_approved = False
            self._current_step_index = 0
            self._verified_steps = []
            self._last_verification = None

            decision = evaluate_workflow_plan(
                plan,
                settings=self.settings,
                observation=self._preview_snapshot,
            )
            self._preview_decision = decision
            if not decision.allowed:
                self._state = SessionState.BLOCKED
                self._narration = self._narrator.policy_block(decision)
                self._remember()
                return self.inspect_current_session()

            review = self._reviewer(plan)
            if not review.approved:
                self._state = SessionState.BLOCKED
                self._narration = _review_block_narration(review)
                self._remember()
                return self.inspect_current_session()

            if _is_answer_only(plan, decision):
                self._state = SessionState.COMPLETED
                self._narration = self._narrator.describe_screen(
                    _desktop_observation(observation)
                )
            elif _needs_reviewer(plan, decision):
                self._state = SessionState.AWAITING_REVIEWER_APPROVAL
                self._narration = self._narrator.describe_plan(plan)
            else:
                self._state = SessionState.AWAITING_WORKFLOW_APPROVAL
                self._narration = self._narrator.confirmation_prompt(plan)

            self._remember()
            return self.inspect_current_session()
        except Exception as exc:  # pragma: no cover - defensive orchestration boundary
            self._state = SessionState.ERROR
            self._narration = NarrationResult(
                summary=f"Session error: {exc}",
                speakable_text=f"Session error: {exc}",
            )
            self._remember()
            return self.inspect_current_session()

    def approve(self, *, actor: str = "user") -> WorkflowSession:
        del actor
        if self._state == SessionState.AWAITING_REVIEWER_APPROVAL:
            return self.inspect_current_session()
        if self._state not in {
            SessionState.AWAITING_WORKFLOW_APPROVAL,
            SessionState.AWAITING_STEP_APPROVAL,
        }:
            return self.inspect_current_session()
        if self._plan is None:
            self._state = SessionState.ERROR
            self._narration = _plain_narration("No workflow is available to approve.")
            return self.inspect_current_session()

        self._workflow_approved = True
        self._state = SessionState.AWAITING_STEP_APPROVAL
        self._narration = self._narrator.next_step(self._plan.steps[self._current_step_index])
        self._remember()
        return self.inspect_current_session()

    def execute_next_step(self) -> WorkflowSession:
        if self._state in {
            SessionState.CANCELLED,
            SessionState.BLOCKED,
            SessionState.COMPLETED,
            SessionState.ERROR,
            SessionState.VERIFICATION_FAILED,
        }:
            return self.inspect_current_session()
        if self._plan is None or not self._plan.steps:
            return self.inspect_current_session()
        if _needs_reviewer(self._plan, self._preview_decision) and not self._reviewer_approved:
            self._state = SessionState.AWAITING_REVIEWER_APPROVAL
            return self.inspect_current_session()
        if not self._workflow_approved:
            self._state = SessionState.AWAITING_WORKFLOW_APPROVAL
            return self.inspect_current_session()
        if self._current_step_index >= len(self._plan.steps):
            self._state = SessionState.COMPLETED
            return self.inspect_current_session()

        step = self._plan.steps[self._current_step_index]
        decision = self._step_safety_decision(step)
        if not decision.allowed:
            self._workflow_approved = False
            self._state = (
                SessionState.AWAITING_REVIEWER_APPROVAL
                if decision.requires_reviewer_approval
                else SessionState.BLOCKED
            )
            self._narration = self._narrator.policy_block(decision)
            self._remember()
            return self.inspect_current_session()
        if decision.requires_reviewer_approval and not self._reviewer_approved:
            self._state = SessionState.AWAITING_REVIEWER_APPROVAL
            self._narration = self._narrator.policy_block(decision)
            return self.inspect_current_session()

        self._state = SessionState.EXECUTING_STEP
        self._executor(step.action)
        verification = self._verify(step)
        self._last_verification = verification
        self._narration = self._narrator.verification(verification)
        if verification.status != "passed":
            self._state = SessionState.VERIFICATION_FAILED
            self._remember()
            return self.inspect_current_session()

        self._verified_steps.append(step.step_id)
        self._current_step_index += 1
        if self._current_step_index >= len(self._plan.steps):
            self._state = SessionState.COMPLETED
        else:
            self._state = SessionState.AWAITING_STEP_APPROVAL
        self._remember()
        return self.inspect_current_session()

    def request_review(self) -> WorkflowSession:
        if self._state != SessionState.AWAITING_REVIEWER_APPROVAL:
            return self.inspect_current_session()
        self._reviewer_requested = True
        self._narration = _plain_narration("Reviewer approval requested.")
        self._remember()
        return self.inspect_current_session()

    def reviewer_approve(self, *, actor: str = "reviewer") -> WorkflowSession:
        del actor
        if self._state != SessionState.AWAITING_REVIEWER_APPROVAL:
            return self.inspect_current_session()
        self._reviewer_approved = True
        self._state = SessionState.AWAITING_WORKFLOW_APPROVAL
        self._narration = _plain_narration(
            "Reviewer approved. User approval is still required before action."
        )
        self._remember()
        return self.inspect_current_session()

    def reviewer_deny(
        self,
        *,
        actor: str = "reviewer",
        reason: str = "Reviewer denied the workflow.",
    ) -> WorkflowSession:
        del actor
        if self._state != SessionState.AWAITING_REVIEWER_APPROVAL:
            return self.inspect_current_session()
        self._reviewer_approved = False
        self._workflow_approved = False
        self._state = SessionState.BLOCKED
        self._narration = _plain_narration(reason)
        self._remember()
        return self.inspect_current_session()

    def cancel(self, reason: str = "Workflow cancelled.") -> WorkflowSession:
        self._workflow_approved = False
        self._reviewer_approved = False
        self._state = SessionState.CANCELLED
        self._narration = _plain_narration(reason)
        self._remember()
        return self.inspect_current_session()

    def inspect_current_session(self) -> WorkflowSession:
        return WorkflowSession(
            session_id=self.session_id,
            state=self._state.value,
            plan=self._plan,
            current_step_id=self._current_step_id(),
            verified_steps=list(self._verified_steps),
            last_verification=self._last_verification,
            narration=self._narration,
        )

    def _observe(self) -> DesktopObservation | Mapping[str, Any]:
        observation = self._observer()
        self._last_observation = observation
        return observation

    def _step_safety_decision(self, step: WorkflowStep) -> SafetyDecision:
        current = self._observe()
        return evaluate_step_before_execution(
            step,
            settings=self.settings,
            preview_decision=self._preview_decision
            or _inform_only_safety("No preview decision was available."),
            preview_snapshot=self._preview_snapshot,
            current_snapshot=_focus_snapshot(current),
        )

    def _verify(self, step: WorkflowStep) -> VerificationResult:
        if not self.settings.verify_after_each_action:
            return VerificationResult(
                status="unknown",
                reason="Verification is disabled in settings.",
                expected=step.expected_outcome,
                actual=None,
                next_recommendation="Continue only after manual review.",
            )
        return self._verifier.verify_step(step)

    def _remember(self) -> None:
        if not self._memory or not self.settings.memory_enabled:
            return
        self._memory.save_session(
            session_id=self.session_id,
            preferences={},
            observation=self._last_observation or self._preview_observation,
            workflow_id=self._plan.workflow_id if self._plan else None,
            workflow_state=self._state.value,
            completed_steps=self._verified_steps,
        )

    def _current_step_id(self) -> str | None:
        if self._plan is None or self._current_step_index >= len(self._plan.steps):
            return None
        if self._state in {SessionState.COMPLETED, SessionState.CANCELLED}:
            return None
        return self._plan.steps[self._current_step_index].step_id

    @staticmethod
    def _unsupported_executor(action: CueAction) -> None:
        if action.action_type in {ActionType.NONE, ActionType.VERIFY}:
            return
        raise RuntimeError("No executor was configured for state-changing actions.")


def _needs_reviewer(
    plan: WorkflowPlan,
    decision: SafetyDecision | None,
) -> bool:
    return (
        plan.requires_reviewer_approval
        or plan.approval_tier == ApprovalTier.GUARDIAN_REQUIRED
        or bool(decision and decision.requires_reviewer_approval)
        or bool(decision and decision.approval_tier == ApprovalTier.GUARDIAN_REQUIRED)
    )


def _is_answer_only(plan: WorkflowPlan, decision: SafetyDecision) -> bool:
    return (
        not plan.workflow_required
        or not plan.steps
        or decision.approval_tier == ApprovalTier.INFORM_ONLY
    )


def _focus_snapshot(
    observation: DesktopObservation | Mapping[str, Any] | None,
) -> FocusSnapshot | None:
    if observation is None:
        return None
    if isinstance(observation, DesktopObservation):
        return FocusSnapshot(
            active_app=observation.active_app or "Unknown",
            active_window=observation.active_window,
            focused_element=_focus_label(observation),
        )
    return FocusSnapshot(
        active_app=str(observation.get("active_app") or observation.get("app") or "Unknown"),
        active_window=observation.get("active_window") or observation.get("window"),
        focused_element=observation.get("focused_element") or observation.get("focus"),
        domain=observation.get("domain"),
    )


def _desktop_observation(
    observation: DesktopObservation | Mapping[str, Any],
) -> DesktopObservation:
    if isinstance(observation, DesktopObservation):
        return observation
    raise TypeError("Narration requires DesktopObservation in the local orchestrator.")


def _focus_label(observation: DesktopObservation) -> str | None:
    focus = observation.focused_element
    return focus.title or focus.value or focus.role


def _review_block_narration(review: PlanReview) -> NarrationResult:
    issues = "; ".join(review.issues) if review.issues else "Plan review failed."
    return _plain_narration(f"Blocked by reviewer: {issues}")


def _plain_narration(text: str) -> NarrationResult:
    return NarrationResult(summary=text, speakable_text=text)


def _inform_only_safety(reason: str) -> SafetyDecision:
    return SafetyDecision(
        allowed=True,
        approval_tier=ApprovalTier.INFORM_ONLY,
        reason=reason,
        risk_reasons=[],
    )
