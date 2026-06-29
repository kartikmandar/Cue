from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from pydantic import ValidationError

from cue.actions import ActionType
from cue.agent_models import PlanReview, WorkflowPlan


class PlanReviewer:
    def __init__(self, *, max_workflow_steps: int = 5) -> None:
        self.max_workflow_steps = max_workflow_steps

    def review(self, plan: WorkflowPlan | Mapping[str, Any]) -> PlanReview:
        parsed = _coerce_plan(plan)
        if isinstance(parsed, PlanReview):
            return parsed

        issues = _review_plan(parsed, max_workflow_steps=self.max_workflow_steps)
        if issues:
            return PlanReview(
                approved=False,
                issues=issues,
                revised_confirmation_prompt=(
                    "I need to revise this workflow before acting."
                ),
            )

        return PlanReview(
            approved=True,
            issues=[],
            revised_confirmation_prompt=parsed.confirmation_prompt,
        )


def review_plan(plan: WorkflowPlan | Mapping[str, Any]) -> PlanReview:
    return PlanReviewer().review(plan)


def _coerce_plan(plan: WorkflowPlan | Mapping[str, Any]) -> WorkflowPlan | PlanReview:
    if isinstance(plan, WorkflowPlan):
        return plan

    try:
        return WorkflowPlan.model_validate(plan)
    except ValidationError as exc:
        return PlanReview(
            approved=False,
            issues=_validation_issues(exc),
            revised_confirmation_prompt="I need a schema-valid workflow before acting.",
        )


def _review_plan(plan: WorkflowPlan, *, max_workflow_steps: int) -> list[str]:
    issues: list[str] = []

    if not plan.allowed_by_policy:
        issues.append(f"Plan is blocked by policy: {plan.policy_reason}")

    if not plan.expected_outcome.strip():
        issues.append("Plan expected outcome is required.")

    if plan.workflow_required and not plan.steps:
        issues.append("Workflow plans must include at least one executable step.")

    if len(plan.steps) > max_workflow_steps:
        issues.append(f"Workflow has more than {max_workflow_steps} steps.")

    for index, step in enumerate(plan.steps):
        if not step.expected_outcome.strip():
            issues.append(f"Step {step.step_id} expected outcome is required.")

        if step.action.action_type == ActionType.NONE and plan.workflow_required:
            issues.append(f"Step {step.step_id} does not contain an executable action.")

        if _needs_verify_follow_up(step.action.action_type, step.action.changes_state):
            next_step = plan.steps[index + 1] if index + 1 < len(plan.steps) else None
            if next_step is None or next_step.action.action_type != ActionType.VERIFY:
                issues.append(
                    f"State-changing step {step.step_id} should be followed "
                    "by a verify step."
                )

    return issues


def _needs_verify_follow_up(action_type: ActionType, changes_state: bool) -> bool:
    if not changes_state:
        return False
    return action_type not in {
        ActionType.ASK_CONFIRMATION,
        ActionType.REQUEST_REVIEWER_APPROVAL,
        ActionType.CANCEL_WORKFLOW,
    }


def _validation_issues(exc: ValidationError) -> list[str]:
    issues: list[str] = []
    for error in exc.errors():
        location = ".".join(str(part) for part in error.get("loc", ()))
        value = error.get("input")
        if location.endswith("action.action_type") or location.endswith("action_type"):
            issues.append(f"unsupported action type: {value}")
        else:
            issues.append(f"Plan is not schema-valid at {location}: {error['msg']}")
    return issues or ["Plan is not schema-valid."]
