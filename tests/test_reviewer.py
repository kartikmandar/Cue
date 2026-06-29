from cue.actions import ActionType, CueAction, WorkflowCategory
from cue.agent_models import IntentResult, NormalizedInput, WorkflowPlan, WorkflowStep
from cue.policy import ApprovalTier
from cue.reviewer import PlanReviewer, review_plan


def make_intent(category=WorkflowCategory.DOCUMENT):
    normalized = NormalizedInput(
        text="Open TextEdit and write a title",
        raw_text="Open TextEdit and write a title",
        input_mode="text",
        source="test",
    )
    return IntentResult(
        normalized_input=normalized,
        intent=category.value,
        workflow_required=category != WorkflowCategory.ANSWER,
        workflow_category=category,
        risk_level="low",
        reason="test intent",
    )


def make_plan(*, steps, expected_outcome="TextEdit contains the title Cue."):
    return WorkflowPlan(
        intent=make_intent(),
        narration="Cue can do this after approval.",
        workflow_required=True,
        workflow_category=WorkflowCategory.DOCUMENT,
        steps=steps,
        risk_level="low",
        approval_tier=ApprovalTier.CONFIRM_EACH_ACTION,
        confirmation_prompt="Approve opening TextEdit and writing the title?",
        expected_outcome=expected_outcome,
        risk_reasons=[],
        requires_reviewer_approval=False,
        redaction_applied=False,
        allowed_by_policy=True,
        policy_reason="TextEdit is allowed.",
        audit_event_summary="TextEdit plan previewed.",
    )


def make_step(
    step_id,
    action_type=ActionType.OPEN_APP,
    expected_outcome="TextEdit is active.",
):
    return WorkflowStep(
        step_id=step_id,
        title=step_id,
        action=CueAction(
            action_type=action_type,
            payload={"app_name": "TextEdit"} if action_type == ActionType.OPEN_APP else {},
            reason="Required for the requested workflow.",
            expected_app="TextEdit",
            changes_state=action_type not in {ActionType.VERIFY, ActionType.NONE},
        ),
        expected_outcome=expected_outcome,
    )


def test_reviewer_approves_minimal_executable_plan():
    plan = make_plan(
        steps=[
            make_step("step-1", ActionType.OPEN_APP, "TextEdit is active."),
            make_step("step-2", ActionType.VERIFY, "TextEdit active window is verified."),
            make_step("step-3", ActionType.TYPE_TEXT, "The title Cue is inserted."),
            make_step("step-4", ActionType.VERIFY, "The title Cue is visible."),
        ]
    )

    review = review_plan(plan)

    assert review.approved is True
    assert review.issues == []
    assert review.revised_confirmation_prompt == plan.confirmation_prompt


def test_reviewer_rejects_plan_without_expected_outcome():
    plan = make_plan(
        steps=[make_step("step-1", ActionType.OPEN_APP, "TextEdit is active.")],
        expected_outcome="",
    )

    review = PlanReviewer().review(plan)

    assert review.approved is False
    assert "Plan expected outcome is required." in review.issues


def test_reviewer_rejects_workflow_required_plan_with_no_steps():
    plan = make_plan(steps=[])

    review = review_plan(plan)

    assert review.approved is False
    assert "Workflow plans must include at least one executable step." in review.issues


def test_reviewer_rejects_unsupported_action_type_from_raw_plan():
    raw_plan = make_plan(steps=[make_step("step-1")]).model_dump(mode="json")
    raw_plan["steps"][0]["action"]["action_type"] = "run_command"

    review = PlanReviewer().review(raw_plan)

    assert review.approved is False
    assert any("unsupported action type" in issue for issue in review.issues)


def test_reviewer_rejects_state_changing_step_without_verify_follow_up():
    plan = make_plan(
        steps=[
            make_step("step-1", ActionType.OPEN_APP, "TextEdit is active."),
            make_step("step-2", ActionType.TYPE_TEXT, "The title Cue is inserted."),
        ]
    )

    review = review_plan(plan)

    assert review.approved is False
    assert "State-changing step step-2 should be followed by a verify step." in review.issues
