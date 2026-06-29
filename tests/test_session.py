from cue.actions import ActionType, CueAction, WorkflowCategory
from cue.agent_models import (
    IntentResult,
    NormalizedInput,
    PlanReview,
    VerificationResult,
    WorkflowPlan,
    WorkflowStep,
)
from cue.config import Settings
from cue.context import DesktopObservation
from cue.focus import CursorPosition, FocusedElement
from cue.memory import SessionMemory
from cue.policy import ApprovalTier
from cue.session import CueSessionOrchestrator, SessionState


class FakeObserver:
    def __init__(self, *observations):
        self.observations = list(observations)
        self.calls = 0

    def __call__(self):
        self.calls += 1
        if len(self.observations) > 1:
            return self.observations.pop(0)
        return self.observations[0]


class FakeExecutor:
    def __init__(self):
        self.calls = []

    def __call__(self, action):
        self.calls.append(action)
        return {"ok": True, "action_type": action.action_type.value}


class FakeVerifier:
    def __init__(self, *results):
        self.results = list(results)
        self.calls = []

    def verify_step(self, step):
        self.calls.append(step.step_id)
        if len(self.results) > 1:
            return self.results.pop(0)
        return self.results[0]


def make_settings(**overrides):
    values = {
        "cerebras_api_key": "test-key",
        "allowed_apps": ["TextEdit", "Finder", "Safari"],
        "blocked_apps": [
            "Keychain Access",
            "1Password",
            "Bitwarden",
            "System Settings",
        ],
        "allowed_domains": ["localhost", "127.0.0.1", "demo.local"],
    }
    values.update(overrides)
    return Settings(**values)


def make_observation(app="TextEdit", window="Untitled", focus="Document body"):
    return DesktopObservation(
        active_app=app,
        active_window=window,
        focused_element=FocusedElement(
            status="known",
            role="AXTextArea",
            title=focus,
            value="Cue draft",
            source="test",
        ),
        cursor_position=CursorPosition(status="known", x=50, y=100, source="test"),
        sources=["test"],
    )


def make_intent(category, text="Open TextEdit and type Cue", workflow_required=True):
    normalized = NormalizedInput(
        text=text,
        raw_text=text,
        input_mode="text",
        source="test",
    )
    return IntentResult(
        normalized_input=normalized,
        intent=category.value,
        workflow_required=workflow_required,
        workflow_category=category,
        risk_level="low",
        reason="test intent",
    )


def make_step(
    step_id,
    action_type=ActionType.TYPE_TEXT,
    *,
    title=None,
    reason="Write the approved text.",
    expected_app="TextEdit",
    expected_window="Untitled",
    expected_focus="Document body",
    payload=None,
):
    return WorkflowStep(
        step_id=step_id,
        title=title or step_id.replace("-", " ").title(),
        action=CueAction(
            action_type=action_type,
            payload=payload or {"text": "Cue"},
            reason=reason,
            expected_app=expected_app,
            expected_window=expected_window,
            expected_focus=expected_focus,
            changes_state=action_type
            not in {ActionType.NONE, ActionType.VERIFY, ActionType.WAIT_FOR_WINDOW},
        ),
        expected_outcome=f"{step_id} is complete.",
        verification_criteria=f"{step_id} is visible.",
    )


def make_plan(
    *,
    steps,
    category=WorkflowCategory.DOCUMENT,
    approval_tier=ApprovalTier.CONFIRM_EACH_ACTION,
    requires_reviewer=False,
    workflow_required=True,
    text="Open TextEdit and type Cue",
):
    return WorkflowPlan(
        intent=make_intent(category, text=text, workflow_required=workflow_required),
        narration="Cue can do this after approval.",
        workflow_required=workflow_required,
        workflow_category=category,
        steps=steps,
        risk_level="low",
        approval_tier=approval_tier,
        confirmation_prompt="Approve this workflow?",
        expected_outcome="The requested outcome is visible.",
        risk_reasons=[],
        requires_reviewer_approval=requires_reviewer,
        redaction_applied=False,
        allowed_by_policy=True,
        policy_reason="Allowed for test.",
        audit_event_summary="Workflow previewed.",
        workflow_id="workflow-1",
    )


def passed():
    return VerificationResult(
        status="passed",
        reason="Expected state matched.",
        expected="TextEdit contains Cue.",
        actual="TextEdit contains Cue.",
        next_recommendation="Continue to the next approved step.",
    )


def failed():
    return VerificationResult(
        status="failed",
        reason="Expected text was missing.",
        expected="TextEdit contains Cue.",
        actual="TextEdit contains Draft.",
        next_recommendation="Pause and re-observe.",
    )


def make_orchestrator(tmp_path, *, plan, observer, executor=None, verifier=None):
    return CueSessionOrchestrator(
        settings=make_settings(),
        observer=observer,
        planner=lambda request, observation: plan,
        reviewer=lambda workflow_plan: PlanReview(
            approved=True,
            issues=[],
            revised_confirmation_prompt=workflow_plan.confirmation_prompt,
        ),
        executor=executor or FakeExecutor(),
        verifier=verifier or FakeVerifier(passed()),
        memory=SessionMemory(tmp_path / ".cue" / "memory.json"),
    )


def test_answer_only_request_completes_without_action_approval_or_execution(tmp_path):
    executor = FakeExecutor()
    plan = make_plan(
        steps=[],
        category=WorkflowCategory.ANSWER,
        approval_tier=ApprovalTier.INFORM_ONLY,
        workflow_required=False,
        text="What is on my screen?",
    )
    session = make_orchestrator(
        tmp_path,
        plan=plan,
        observer=FakeObserver(make_observation()),
        executor=executor,
    )

    result = session.preview("What is on my screen?")

    assert result.state == SessionState.COMPLETED.value
    assert executor.calls == []
    assert "TextEdit" in result.narration.speakable_text


def test_multi_step_workflow_requires_approval_before_execution(tmp_path):
    executor = FakeExecutor()
    plan = make_plan(
        steps=[
            make_step(
                "step-1",
                ActionType.OPEN_APP,
                title="Open TextEdit",
                payload={"app_name": "TextEdit"},
            ),
            make_step("step-2", ActionType.TYPE_TEXT, title="Type Cue"),
        ]
    )
    session = make_orchestrator(
        tmp_path,
        plan=plan,
        observer=FakeObserver(make_observation()),
        executor=executor,
        verifier=FakeVerifier(passed(), passed()),
    )

    preview = session.preview("Open TextEdit and type Cue")
    before_approval = session.execute_next_step()
    approved = session.approve(actor="user")
    first = session.execute_next_step()
    second = session.execute_next_step()

    assert preview.state == SessionState.AWAITING_WORKFLOW_APPROVAL.value
    assert before_approval.state == SessionState.AWAITING_WORKFLOW_APPROVAL.value
    assert executor.calls[0].action_type == ActionType.OPEN_APP
    assert approved.state == SessionState.AWAITING_STEP_APPROVAL.value
    assert first.state == SessionState.AWAITING_STEP_APPROVAL.value
    assert first.verified_steps == ["step-1"]
    assert second.state == SessionState.COMPLETED.value
    assert second.verified_steps == ["step-1", "step-2"]


def test_focus_drift_blocks_pending_action_without_execution(tmp_path):
    executor = FakeExecutor()
    plan = make_plan(steps=[make_step("step-1")])
    session = make_orchestrator(
        tmp_path,
        plan=plan,
        observer=FakeObserver(
            make_observation("TextEdit", "Untitled", "Document body"),
            make_observation("Safari", "Dashboard", "Search field"),
        ),
        executor=executor,
    )

    session.preview("Open TextEdit and type Cue")
    session.approve(actor="user")
    result = session.execute_next_step()

    assert result.state == SessionState.BLOCKED.value
    assert executor.calls == []
    assert "focus drift" in result.narration.speakable_text.casefold()


def test_verification_failure_pauses_workflow_after_execution(tmp_path):
    executor = FakeExecutor()
    plan = make_plan(steps=[make_step("step-1")])
    session = make_orchestrator(
        tmp_path,
        plan=plan,
        observer=FakeObserver(make_observation()),
        executor=executor,
        verifier=FakeVerifier(failed()),
    )

    session.preview("Open TextEdit and type Cue")
    session.approve(actor="user")
    result = session.execute_next_step()

    assert result.state == SessionState.VERIFICATION_FAILED.value
    assert len(executor.calls) == 1
    assert result.last_verification.status == "failed"
    assert "Verification failed" in result.narration.speakable_text


def test_reviewer_required_flow_gates_execution_until_reviewer_and_user_approve(
    tmp_path,
):
    executor = FakeExecutor()
    plan = make_plan(
        steps=[
            make_step(
                "step-1",
                ActionType.HOTKEY,
                title="Prepare release action",
                reason="Prepare a deploy release action.",
                payload={"keys": ["command", "r"]},
            )
        ],
        approval_tier=ApprovalTier.GUARDIAN_REQUIRED,
        requires_reviewer=True,
        text="Prepare deploy release",
    )
    session = make_orchestrator(
        tmp_path,
        plan=plan,
        observer=FakeObserver(make_observation()),
        executor=executor,
    )

    preview = session.preview("Prepare deploy release")
    before_review = session.execute_next_step()
    requested = session.request_review()
    reviewer_approved = session.reviewer_approve(actor="guardian")
    user_approved = session.approve(actor="user")
    executed = session.execute_next_step()

    assert preview.state == SessionState.AWAITING_REVIEWER_APPROVAL.value
    assert before_review.state == SessionState.AWAITING_REVIEWER_APPROVAL.value
    assert requested.state == SessionState.AWAITING_REVIEWER_APPROVAL.value
    assert reviewer_approved.state == SessionState.AWAITING_WORKFLOW_APPROVAL.value
    assert user_approved.state == SessionState.AWAITING_STEP_APPROVAL.value
    assert executed.state == SessionState.COMPLETED.value
    assert len(executor.calls) == 1


def test_cancel_expires_pending_workflow_and_prevents_later_execution(tmp_path):
    executor = FakeExecutor()
    plan = make_plan(steps=[make_step("step-1")])
    session = make_orchestrator(
        tmp_path,
        plan=plan,
        observer=FakeObserver(make_observation()),
        executor=executor,
    )

    session.preview("Open TextEdit and type Cue")
    cancelled = session.cancel("user cancelled")
    result = session.execute_next_step()

    assert cancelled.state == SessionState.CANCELLED.value
    assert result.state == SessionState.CANCELLED.value
    assert executor.calls == []
