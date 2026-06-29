from cue.actions import ActionType, CueAction, WorkflowCategory
from cue.agent_models import (
    IntentResult,
    NormalizedInput,
    PlanReview,
    VerificationResult,
    WorkflowPlan,
    WorkflowStep,
)
from cue.backend import CueBackend, SessionNotFound
from cue.config import Settings
from cue.context import DesktopObservation
from cue.focus import CursorPosition, FocusedElement
from cue.policy import ApprovalTier
from cue.session import SessionState


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
        "memory_enabled": False,
        "audit_log": False,
        "allowed_apps": ["TextEdit", "Finder", "Safari", "Terminal"],
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
        cursor_position=CursorPosition(status="known", x=12, y=34, source="test"),
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
    step_id="step-1",
    action_type=ActionType.TYPE_TEXT,
    *,
    title="Type Cue",
    expected_app="TextEdit",
    expected_window="Untitled",
    expected_focus="Document body",
    payload=None,
):
    return WorkflowStep(
        step_id=step_id,
        title=title,
        action=CueAction(
            action_type=action_type,
            payload=payload or {"text": "Cue"},
            reason="Do the approved local-safe action.",
            expected_app=expected_app,
            expected_window=expected_window,
            expected_focus=expected_focus,
            changes_state=action_type
            not in {ActionType.NONE, ActionType.VERIFY, ActionType.WAIT_FOR_WINDOW},
        ),
        expected_outcome=f"{title} is complete.",
        verification_criteria=f"{title} is visible.",
    )


def make_plan(
    *,
    steps=None,
    category=WorkflowCategory.DOCUMENT,
    approval_tier=ApprovalTier.CONFIRM_EACH_ACTION,
    requires_reviewer=False,
    workflow_required=True,
    text="Open TextEdit and type Cue",
    audit_event_summary="Workflow preview for user@example.com with token sk-test-secret00.",
):
    steps = [make_step()] if steps is None else steps
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
        audit_event_summary=audit_event_summary,
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


def make_backend(*, plan=None, observer=None, executor=None, verifier=None):
    workflow_plan = plan or make_plan()
    return CueBackend(
        settings=make_settings(),
        observer=observer or FakeObserver(make_observation()),
        planner=lambda request, observation: workflow_plan,
        reviewer=lambda candidate: PlanReview(
            approved=True,
            issues=[],
            revised_confirmation_prompt=candidate.confirmation_prompt,
        ),
        executor=executor or FakeExecutor(),
        verifier=verifier or FakeVerifier(passed()),
    )


def test_preview_returns_workflow_plan_focus_and_narration():
    backend = make_backend()

    response = backend.preview("Open TextEdit and type Cue")

    assert response["session_id"]
    assert response["state"] == SessionState.AWAITING_WORKFLOW_APPROVAL.value
    assert response["workflow_plan"]["steps"][0]["title"] == "Type Cue"
    assert response["focus"]["active_app"] == "TextEdit"
    assert response["focus"]["active_window"] == "Untitled"
    assert response["focus"]["focused_element"]["title"] == "Document body"
    assert response["narration"]["speakable_text"] == "Approve this workflow?"
    assert response["risk"]["approval_tier"] == ApprovalTier.CONFIRM_EACH_ACTION.value
    assert response["policy_decision"]["allowed"] is True
    assert response["audit_summary"]


def test_approve_stores_workflow_approval():
    backend = make_backend()
    preview = backend.preview("Open TextEdit and type Cue")

    approved = backend.approve(preview["session_id"], actor="user")
    inspected = backend.get_session(preview["session_id"])

    assert approved["state"] == SessionState.AWAITING_STEP_APPROVAL.value
    assert inspected["state"] == SessionState.AWAITING_STEP_APPROVAL.value
    assert inspected["current_step_id"] == "step-1"
    assert "Next step" in approved["narration"]["speakable_text"]


def test_next_executes_one_approved_step_and_returns_verification():
    executor = FakeExecutor()
    verifier = FakeVerifier(passed())
    backend = make_backend(executor=executor, verifier=verifier)
    preview = backend.preview("Open TextEdit and type Cue")
    backend.approve(preview["session_id"], actor="user")

    response = backend.next(preview["session_id"])

    assert response["state"] == SessionState.COMPLETED.value
    assert executor.calls[0].action_type == ActionType.TYPE_TEXT
    assert verifier.calls == ["step-1"]
    assert response["last_verification"]["status"] == "passed"
    assert response["verified_steps"] == ["step-1"]


def test_reviewer_denial_blocks_pending_workflow():
    plan = make_plan(
        approval_tier=ApprovalTier.GUARDIAN_REQUIRED,
        requires_reviewer=True,
    )
    backend = make_backend(plan=plan)
    preview = backend.preview("Prepare release action")

    requested = backend.request_review(preview["session_id"])
    denied = backend.confirm_reviewer(
        preview["session_id"],
        approved=False,
        actor="guardian",
        reason="Reviewer denied this workflow.",
    )

    assert preview["state"] == SessionState.AWAITING_REVIEWER_APPROVAL.value
    assert requested["state"] == SessionState.AWAITING_REVIEWER_APPROVAL.value
    assert denied["state"] == SessionState.BLOCKED.value
    assert "Reviewer denied" in denied["narration"]["speakable_text"]


def test_reviewer_approval_still_requires_user_approval_before_next():
    executor = FakeExecutor()
    plan = make_plan(
        approval_tier=ApprovalTier.GUARDIAN_REQUIRED,
        requires_reviewer=True,
    )
    backend = make_backend(plan=plan, executor=executor)
    preview = backend.preview("Prepare release action")

    reviewer = backend.confirm_reviewer(preview["session_id"], approved=True)
    before_user = backend.next(preview["session_id"])
    user = backend.approve(preview["session_id"])
    executed = backend.next(preview["session_id"])

    assert reviewer["state"] == SessionState.AWAITING_WORKFLOW_APPROVAL.value
    assert before_user["state"] == SessionState.AWAITING_WORKFLOW_APPROVAL.value
    assert user["state"] == SessionState.AWAITING_STEP_APPROVAL.value
    assert executed["state"] == SessionState.COMPLETED.value
    assert len(executor.calls) == 1


def test_cancel_marks_pending_workflow_cancelled_and_prevents_execution():
    executor = FakeExecutor()
    backend = make_backend(executor=executor)
    preview = backend.preview("Open TextEdit and type Cue")

    cancelled = backend.cancel(preview["session_id"], reason="User cancelled.")
    after_cancel = backend.next(preview["session_id"])

    assert cancelled["state"] == SessionState.CANCELLED.value
    assert after_cancel["state"] == SessionState.CANCELLED.value
    assert executor.calls == []


def test_invalid_session_ids_are_handled_clearly():
    backend = make_backend()

    try:
        backend.get_session("missing-session")
    except SessionNotFound as exc:
        assert "missing-session" in str(exc)
    else:
        raise AssertionError("missing session should raise SessionNotFound")


def test_audit_events_are_redacted_and_session_scoped():
    backend = make_backend()
    first = backend.preview("Open TextEdit and type Cue")
    second = backend.preview("Open TextEdit again")

    first_events = backend.audit_events(first["session_id"])
    second_events = backend.audit_events(second["session_id"])

    assert first_events
    assert second_events
    assert all(event["session_id"] == first["session_id"] for event in first_events)
    assert all(event["session_id"] == second["session_id"] for event in second_events)
    combined = " ".join(event["summary"] for event in first_events + second_events)
    assert "user@example.com" not in combined
    assert "sk-test-secret00" not in combined
