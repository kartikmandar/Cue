from cue.actions import ActionType, CueAction, WorkflowCategory
from cue.agent_models import (
    IntentResult,
    NormalizedInput,
    VerificationResult,
    WorkflowPlan,
    WorkflowStep,
)
from cue.context import DesktopObservation
from cue.focus import CursorPosition, FocusedElement
from cue.narrator import Narrator
from cue.policy import ApprovalTier
from cue.safety import SafetyDecision


def make_observation():
    return DesktopObservation(
        active_app="TextEdit",
        active_window="Untitled",
        focused_element=FocusedElement(
            status="known",
            role="AXTextArea",
            title="Document body",
            value="Cue draft",
            source="test",
        ),
        cursor_position=CursorPosition(status="known", x=80, y=160, source="test"),
        sources=["test"],
    )


def make_plan():
    normalized = NormalizedInput(
        text="Open TextEdit and type Cue",
        raw_text="Open TextEdit and type Cue",
        input_mode="text",
        source="test",
    )
    intent = IntentResult(
        normalized_input=normalized,
        intent="document",
        workflow_required=True,
        workflow_category=WorkflowCategory.DOCUMENT,
        risk_level="low",
        reason="The request edits a local document.",
    )
    step = WorkflowStep(
        step_id="step-1",
        title="Type Cue",
        action=CueAction(
            action_type=ActionType.TYPE_TEXT,
            payload={"text": "Cue"},
            reason="Write the approved title.",
            expected_app="TextEdit",
            expected_window="Untitled",
            expected_focus="Document body",
            changes_state=True,
        ),
        expected_outcome="Cue is visible in the document.",
    )
    return WorkflowPlan(
        intent=intent,
        narration="I will type Cue in TextEdit after approval.",
        workflow_required=True,
        workflow_category=WorkflowCategory.DOCUMENT,
        steps=[step],
        risk_level="low",
        approval_tier=ApprovalTier.CONFIRM_EACH_ACTION,
        confirmation_prompt="Approve typing Cue in TextEdit?",
        expected_outcome="TextEdit contains Cue.",
        risk_reasons=["document editing changes state"],
        requires_reviewer_approval=False,
        redaction_applied=False,
        allowed_by_policy=True,
        policy_reason="TextEdit is allowed.",
        audit_event_summary="TextEdit plan previewed.",
        workflow_id="workflow-1",
    )


def test_narrates_current_screen_focus_without_cursor_coordinates():
    narration = Narrator().describe_screen(make_observation())

    assert "TextEdit" in narration.speakable_text
    assert "Untitled" in narration.speakable_text
    assert "Document body" in narration.speakable_text
    assert "80, 160" not in narration.speakable_text
    assert "Cursor:" not in narration.speakable_text


def test_screen_narration_omits_driver_diagnostics_when_focus_is_unknown():
    observation = DesktopObservation(
        active_app="CueApp",
        active_window="Cue",
        focused_element=FocusedElement(
            status="unknown",
            source="cua:get_window_state",
            reason=(
                "Cua Driver 0.6.8 does not expose a standalone focused element "
                "tool; focus must be inferred from the AX window state."
            ),
        ),
        cursor_position=CursorPosition(status="known", x=802, y=638, source="test"),
        sources=["test"],
    )

    narration = Narrator().describe_screen(observation)

    assert narration.speakable_text == "Current screen: CueApp, window Cue."


def test_narrates_plan_confirmation_block_verification_and_next_step():
    narrator = Narrator()
    plan = make_plan()
    block = SafetyDecision(
        allowed=False,
        approval_tier=ApprovalTier.BLOCKED,
        reason="Blocked because a sensitive app is active.",
        risk_reasons=["sensitive app blocks screenshots and actions"],
        action_allowed=False,
    )
    failed = VerificationResult(
        status="failed",
        reason="TextEdit did not contain Cue.",
        expected="TextEdit contains Cue.",
        actual="TextEdit contains Draft.",
        next_recommendation="Pause and re-observe.",
    )

    plan_text = narrator.describe_plan(plan).speakable_text
    confirmation = narrator.confirmation_prompt(plan).speakable_text
    block_text = narrator.policy_block(block).speakable_text
    verification = narrator.verification(failed).speakable_text
    next_step = narrator.next_step(plan.steps[0]).speakable_text

    assert "1 step" in plan_text
    assert "Type Cue" in plan_text
    assert "Approve typing Cue" in confirmation
    assert "Blocked" in block_text
    assert "sensitive app" in block_text
    assert "Verification failed" in verification
    assert "Pause and re-observe" in verification
    assert "Next step: Type Cue" in next_step
