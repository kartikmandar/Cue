from fastapi.testclient import TestClient

from cue.actions import ActionType, CueAction, WorkflowCategory
from cue.agent_models import (
    IntentResult,
    NormalizedInput,
    PlanReview,
    VerificationResult,
    WorkflowPlan,
    WorkflowStep,
)
from cue.api import create_app
from cue.backend import CueBackend
from cue.config import Settings
from cue.context import DesktopObservation
from cue.focus import CursorPosition, FocusedElement
from cue.policy import ApprovalTier
from cue.session import SessionState


class FakeObserver:
    def __init__(self):
        self.calls = 0

    def __call__(self):
        self.calls += 1
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
            cursor_position=CursorPosition(status="known", x=20, y=40, source="test"),
            sources=["test"],
        )


class FakeExecutor:
    def __call__(self, action):
        return {"ok": True, "action_type": action.action_type.value}


class FakeVerifier:
    def verify_step(self, step):
        return VerificationResult(
            status="passed",
            reason="Expected state matched.",
            expected=step.expected_outcome,
            actual=step.expected_outcome,
        )


def make_settings(**overrides):
    values = {
        "cerebras_api_key": "test-key",
        "memory_enabled": False,
        "audit_log": False,
        "allowed_apps": ["TextEdit", "Finder", "Safari", "Terminal"],
        "blocked_apps": ["Keychain Access", "1Password", "Bitwarden"],
        "allowed_domains": ["localhost", "127.0.0.1"],
    }
    values.update(overrides)
    return Settings(**values)


def make_plan(request, observation):
    del observation
    normalized = NormalizedInput(text=request, raw_text=request, source="chat")
    intent = IntentResult(
        normalized_input=normalized,
        intent=WorkflowCategory.APP_LAUNCH.value,
        workflow_required=True,
        workflow_category=WorkflowCategory.APP_LAUNCH,
        risk_level="low",
        reason="test action",
    )
    step = WorkflowStep(
        step_id="open-textedit",
        title="Open TextEdit",
        action=CueAction(
            action_type=ActionType.OPEN_APP,
            payload={"app_name": "TextEdit"},
            reason="Open TextEdit after approval.",
            expected_app="TextEdit",
            changes_state=True,
        ),
        expected_outcome="TextEdit is active.",
        verification_criteria="Active app is TextEdit.",
    )
    return WorkflowPlan(
        intent=intent,
        narration="Cue can open TextEdit after approval.",
        workflow_required=True,
        workflow_category=WorkflowCategory.APP_LAUNCH,
        steps=[step],
        risk_level="low",
        approval_tier=ApprovalTier.CONFIRM_EACH_ACTION,
        confirmation_prompt="Approve opening TextEdit?",
        expected_outcome="TextEdit is active.",
        risk_reasons=[],
        requires_reviewer_approval=False,
        redaction_applied=False,
        allowed_by_policy=True,
        policy_reason="Allowed for test.",
        audit_event_summary="TextEdit open previewed.",
        workflow_id="workflow-chat",
    )


def make_backend(observer=None):
    return CueBackend(
        settings=make_settings(),
        observer=observer or FakeObserver(),
        planner=make_plan,
        reviewer=lambda candidate: PlanReview(
            approved=True,
            issues=[],
            revised_confirmation_prompt=candidate.confirmation_prompt,
        ),
        executor=FakeExecutor(),
        verifier=FakeVerifier(),
    )


def test_chat_answers_casual_greeting_without_observing_desktop():
    observer = FakeObserver()
    backend = make_backend(observer=observer)

    response = backend.chat("Hey Cue, how are you?")

    assert response["mode"] == "conversation"
    assert response["session"] is None
    assert "voice" in response["assistant_message"].casefold()
    assert response["suggested_replies"]
    assert observer.calls == 0


def test_chat_capability_help_mentions_approval_and_text_fallback():
    backend = make_backend()

    response = backend.chat("What can you do?")

    assert response["mode"] == "conversation"
    assert "approve" in response["assistant_message"].casefold()
    assert "type" in response["assistant_message"].casefold()
    assert response["conversation_id"]


def test_chat_routes_action_request_to_preview_session():
    backend = make_backend()

    response = backend.chat("Open TextEdit")

    assert response["mode"] == "action_preview"
    assert response["session"]["state"] == SessionState.AWAITING_WORKFLOW_APPROVAL.value
    assert response["session"]["workflow_plan"]["steps"][0]["title"] == "Open TextEdit"
    assert "approve" in response["assistant_message"].casefold()


def test_chat_endpoint_returns_conversation_or_action_payloads():
    client = TestClient(create_app(backend=make_backend()))

    casual = client.post("/chat", json={"request": "hello"}).json()
    action = client.post("/chat", json={"request": "Open TextEdit"}).json()

    assert casual["mode"] == "conversation"
    assert casual["session"] is None
    assert action["mode"] == "action_preview"
    assert action["session"]["session_id"]


def test_chat_endpoint_rejects_blank_request():
    client = TestClient(create_app(backend=make_backend()))

    response = client.post("/chat", json={"request": "   "})

    assert response.status_code == 400
    assert "request text is required" in response.json()["detail"]
