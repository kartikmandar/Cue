from cue.actions import ActionType, CueAction, WorkflowCategory
from cue.agent_models import (
    IntentResult,
    NarrationResult,
    NormalizedInput,
    PlanReview,
    PolicyDecision,
    VerificationResult,
    WorkflowPlan,
    WorkflowSession,
    WorkflowStep,
)
from cue.policy import ApprovalTier, PolicyDecision as ExistingPolicyDecision


def test_agent_models_reuse_existing_policy_decision_type():
    assert PolicyDecision is ExistingPolicyDecision


def test_workflow_plan_includes_task_6_required_fields():
    normalized = NormalizedInput(
        text="Open TextEdit and write a title",
        raw_text="  Open TextEdit and write a title  ",
        input_mode="text",
        source="command_palette",
    )
    intent = IntentResult(
        normalized_input=normalized,
        intent="document",
        workflow_required=True,
        workflow_category=WorkflowCategory.DOCUMENT,
        risk_level="low",
        reason="The request opens an app and edits a local document.",
    )
    step = WorkflowStep(
        step_id="step-1",
        title="Open TextEdit",
        action=CueAction(
            action_type=ActionType.OPEN_APP,
            payload={"app_name": "TextEdit"},
            reason="The user asked to work in TextEdit.",
            expected_app="TextEdit",
            changes_state=True,
        ),
        expected_outcome="TextEdit is active.",
    )

    plan = WorkflowPlan(
        intent=intent,
        narration="I can open TextEdit and prepare the title after approval.",
        workflow_required=True,
        workflow_category=WorkflowCategory.DOCUMENT,
        steps=[step],
        risk_level="low",
        approval_tier=ApprovalTier.CONFIRM_EACH_ACTION,
        confirmation_prompt="Approve opening TextEdit and writing the title?",
        expected_outcome="TextEdit contains the approved title.",
        risk_reasons=["document editing changes state"],
        requires_reviewer_approval=False,
        redaction_applied=False,
        allowed_by_policy=True,
        policy_reason="Configured desktop action requires user confirmation.",
        audit_event_summary="TextEdit document workflow previewed.",
    )

    assert plan.intent.workflow_category == WorkflowCategory.DOCUMENT
    assert plan.workflow_required is True
    assert plan.steps[0].action.action_type == ActionType.OPEN_APP
    assert plan.confirmation_prompt.startswith("Approve opening TextEdit")
    assert plan.expected_outcome == "TextEdit contains the approved title."
    assert plan.allowed_by_policy is True


def test_plan_review_verification_narration_and_session_models_are_structured():
    review = PlanReview(
        approved=False,
        issues=["Step 2 has no expected outcome."],
        revised_confirmation_prompt="Review the corrected workflow before acting.",
    )
    verification = VerificationResult(
        status="failed",
        reason="TextEdit did not become active.",
        expected="TextEdit active window",
        actual="Finder active window",
        next_recommendation="Re-observe before retrying.",
    )
    narration = NarrationResult(
        summary="TextEdit was not active, so Cue paused.",
        speakable_text="TextEdit was not active. I paused before typing.",
        redaction_applied=False,
    )
    session = WorkflowSession(
        session_id="session-1",
        state="verification_failed",
        plan=None,
        current_step_id="step-1",
        verified_steps=[],
    )

    assert review.approved is False
    assert verification.status == "failed"
    assert narration.speakable_text.startswith("TextEdit was not active")
    assert session.state == "verification_failed"
