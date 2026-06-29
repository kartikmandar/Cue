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
    def __init__(self, *observations):
        self.observations = list(observations)

    def __call__(self):
        if len(self.observations) > 1:
            return self.observations.pop(0)
        return self.observations[0]


class FakeExecutor:
    def __init__(self):
        self.calls = []

    def __call__(self, action):
        self.calls.append(action)
        return {"ok": True}


class FakeVerifier:
    def verify_step(self, step):
        return VerificationResult(
            status="passed",
            reason=f"{step.step_id} matched.",
            expected=step.expected_outcome,
            actual=step.expected_outcome,
            next_recommendation="Continue.",
        )


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
        "allowed_domains": ["localhost", "127.0.0.1"],
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
        cursor_position=CursorPosition(status="known", x=20, y=40, source="test"),
        sources=["test"],
    )


def make_plan(
    request,
    observation,
    *,
    expected_app="TextEdit",
    approval_tier=ApprovalTier.CONFIRM_EACH_ACTION,
    requires_reviewer=False,
    audit_event_summary="Preview includes person@example.com bearer abc123secret.",
):
    del observation
    normalized = NormalizedInput(
        text=request,
        raw_text=request,
        input_mode="text",
        source="test",
    )
    intent = IntentResult(
        normalized_input=normalized,
        intent=WorkflowCategory.DOCUMENT.value,
        workflow_required=True,
        workflow_category=WorkflowCategory.DOCUMENT,
        risk_level="low",
        reason="test intent",
    )
    step = WorkflowStep(
        step_id="step-1",
        title="Type Cue",
        action=CueAction(
            action_type=ActionType.TYPE_TEXT,
            payload={"text": "Cue"},
            reason="Type the approved text.",
            expected_app=expected_app,
            expected_window="Untitled",
            expected_focus="Document body",
            changes_state=True,
        ),
        expected_outcome="Cue is visible.",
        verification_criteria="Cue is visible in TextEdit.",
    )
    return WorkflowPlan(
        intent=intent,
        narration="Cue can do this after approval.",
        workflow_required=True,
        workflow_category=WorkflowCategory.DOCUMENT,
        steps=[step],
        risk_level="low",
        approval_tier=approval_tier,
        confirmation_prompt="Approve this workflow?",
        expected_outcome="Cue is visible.",
        risk_reasons=[],
        requires_reviewer_approval=requires_reviewer,
        redaction_applied=False,
        allowed_by_policy=True,
        policy_reason="Allowed for test.",
        audit_event_summary=audit_event_summary,
        workflow_id="workflow-api",
    )


def make_client(*, planner=None, observer=None, executor=None, settings=None):
    backend = CueBackend(
        settings=settings or make_settings(),
        observer=observer or FakeObserver(make_observation()),
        planner=planner or make_plan,
        reviewer=lambda candidate: PlanReview(
            approved=True,
            issues=[],
            revised_confirmation_prompt=candidate.confirmation_prompt,
        ),
        executor=executor or FakeExecutor(),
        verifier=FakeVerifier(),
    )
    return TestClient(create_app(backend=backend)), backend


def test_health_endpoint():
    client, _backend = make_client()

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "app": "cue",
        "yolo_mode": False,
        "model_provider": "cerebras",
        "model": "gemma-4-31b",
    }


def test_mode_endpoint_updates_yolo_mode_and_existing_sessions():
    executor = FakeExecutor()
    client, _backend = make_client(executor=executor)
    preview = client.post("/session/preview", json={"request": "Type Cue"}).json()
    session_id = preview["session_id"]

    mode = client.post("/mode", json={"yolo_mode": True}).json()
    next_response = client.post("/session/next", json={"session_id": session_id}).json()

    assert mode == {
        "yolo_mode": True,
        "model_provider": "cerebras",
        "model": "gemma-4-31b",
    }
    assert next_response["state"] == SessionState.COMPLETED.value
    assert len(executor.calls) == 1


def test_mode_endpoint_switches_model_provider_when_key_is_available():
    client, _backend = make_client(
        settings=make_settings(openrouter_api_key="test-openrouter-key")
    )

    mode = client.post("/mode", json={"model_provider": "openrouter"}).json()
    inspected = client.get("/mode").json()

    assert mode == {
        "yolo_mode": False,
        "model_provider": "openrouter",
        "model": "google/gemma-4-31b-it:free",
    }
    assert inspected == mode


def test_mode_endpoint_rejects_openrouter_without_api_key():
    client, _backend = make_client()

    response = client.post("/mode", json={"model_provider": "openrouter"})

    assert response.status_code == 400
    assert "OPENROUTER_API_KEY" in response.json()["detail"]


def test_preview_response_shape():
    client, _backend = make_client()

    response = client.post("/session/preview", json={"request": "Type Cue"})

    payload = response.json()
    assert response.status_code == 200
    assert payload["session_id"]
    assert payload["state"] == SessionState.AWAITING_WORKFLOW_APPROVAL.value
    assert payload["workflow_plan"]["steps"][0]["action"]["action_type"] == "type_text"
    assert payload["focus"]["active_app"] == "TextEdit"
    assert payload["confirmation_prompt"] == "Approve this workflow?"
    assert payload["timing"]["backend_ms"] >= 0


def test_approve_next_cancel_and_session_endpoints():
    executor = FakeExecutor()
    client, _backend = make_client(executor=executor)
    preview = client.post("/session/preview", json={"request": "Type Cue"}).json()
    session_id = preview["session_id"]

    approved = client.post("/session/approve", json={"session_id": session_id}).json()
    next_response = client.post("/session/next", json={"session_id": session_id}).json()
    inspected = client.get(f"/session/{session_id}").json()
    cancelled = client.post(
        "/session/cancel",
        json={"session_id": session_id, "reason": "User closed the palette."},
    ).json()

    assert approved["state"] == SessionState.AWAITING_STEP_APPROVAL.value
    assert next_response["state"] == SessionState.COMPLETED.value
    assert inspected["last_verification"]["status"] == "passed"
    assert cancelled["state"] == SessionState.CANCELLED.value
    assert len(executor.calls) == 1


def test_reviewer_endpoints_support_confirmation_and_denial():
    def guardian_plan(request, observation):
        return make_plan(
            request,
            observation,
            approval_tier=ApprovalTier.GUARDIAN_REQUIRED,
            requires_reviewer=True,
        )

    client, _backend = make_client(planner=guardian_plan)
    preview = client.post(
        "/session/preview", json={"request": "Prepare release"}
    ).json()

    requested = client.post(
        "/session/request-review",
        json={"session_id": preview["session_id"]},
    ).json()
    denied = client.post(
        "/session/confirm-reviewer",
        json={
            "session_id": preview["session_id"],
            "approved": False,
            "reason": "Guardian denied.",
        },
    ).json()

    assert preview["state"] == SessionState.AWAITING_REVIEWER_APPROVAL.value
    assert requested["state"] == SessionState.AWAITING_REVIEWER_APPROVAL.value
    assert denied["state"] == SessionState.BLOCKED.value


def test_invalid_session_ids_return_404():
    client, _backend = make_client()

    response = client.post("/session/approve", json={"session_id": "missing"})

    assert response.status_code == 404
    assert "missing" in response.json()["detail"]


def test_policy_blocks_return_200_with_blocked_state():
    def blocked_plan(request, observation):
        return make_plan(request, observation, expected_app="Keychain Access")

    client, _backend = make_client(planner=blocked_plan)

    response = client.post("/session/preview", json={"request": "Type password"})

    payload = response.json()
    assert response.status_code == 200
    assert payload["state"] == SessionState.BLOCKED.value
    assert payload["policy_decision"]["allowed"] is False


def test_audit_endpoint_returns_redacted_session_safe_events():
    client, _backend = make_client()
    preview = client.post("/session/preview", json={"request": "Type Cue"}).json()

    response = client.get(
        "/audit/events",
        params={"session_id": preview["session_id"]},
    )

    events = response.json()["events"]
    combined = " ".join(event["summary"] for event in events)
    assert response.status_code == 200
    assert events
    assert all(event["session_id"] == preview["session_id"] for event in events)
    assert "person@example.com" not in combined
    assert "abc123secret" not in combined
