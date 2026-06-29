import json
from types import SimpleNamespace

from cue.actions import ActionType, WorkflowCategory
from cue.config import Settings
from cue.input_agent import normalize_input
from cue.intent_agent import classify_intent
from cue.planner import WorkflowPlanner
from cue.policy import ApprovalTier


class FakeClient:
    def __init__(self, payload):
        self.payload = payload
        self.calls = []

    def complete(self, messages, *, response_format=None):
        self.calls.append({"messages": messages, "response_format": response_format})
        return SimpleNamespace(
            text=json.dumps(self.payload),
            latency_ms=12,
            usage={"total_tokens": 42},
            time_info={"total_time": 0.012},
        )


def make_settings(**overrides):
    values = {"cerebras_api_key": "test-key", "max_workflow_steps": 5}
    values.update(overrides)
    return Settings(**values)


def plan_payload(*, steps, category="document", required=True):
    return {
        "intent": {
            "normalized_input": {
                "text": "Open TextEdit and write a title",
                "raw_text": "Open TextEdit and write a title",
                "input_mode": "text",
                "source": "test",
            },
            "intent": category,
            "workflow_required": required,
            "workflow_category": category,
            "risk_level": "low" if required else "none",
            "reason": "model classified the request",
            "risk_reasons": [],
        },
        "narration": "I will prepare a short approved workflow.",
        "workflow_required": required,
        "workflow_category": category,
        "steps": steps,
        "risk_level": "low" if required else "none",
        "approval_tier": "confirm_each_action" if required else "inform_only",
        "confirmation_prompt": "Approve this workflow?",
        "expected_outcome": "The requested state is visible and verified.",
        "risk_reasons": [],
        "requires_reviewer_approval": False,
        "redaction_applied": False,
        "allowed_by_policy": True,
        "policy_reason": "Allowed for the demo.",
        "audit_event_summary": "Workflow previewed.",
    }


def workflow_step(step_id, action_type, expected_outcome, payload=None):
    return {
        "step_id": step_id,
        "title": step_id.replace("-", " ").title(),
        "action": {
            "action_type": action_type,
            "payload": payload or {},
            "reason": f"Perform {action_type}.",
            "expected_app": "TextEdit",
            "changes_state": action_type not in {"verify", "none"},
        },
        "expected_outcome": expected_outcome,
        "verification_criteria": expected_outcome,
    }


def test_planner_prompts_with_context_policy_and_json_schema():
    client = FakeClient(
        plan_payload(
            steps=[
                workflow_step(
                    "step-1",
                    "open_app",
                    "TextEdit is active.",
                    {"app_name": "TextEdit"},
                ),
                workflow_step("step-2", "verify", "TextEdit active window is verified."),
            ]
        )
    )
    normalized = normalize_input("Open TextEdit and write a title")
    intent = classify_intent(normalized)

    plan = WorkflowPlanner(client=client, settings=make_settings()).create_plan(
        normalized_input=normalized,
        intent=intent,
        observation_context="Active: Finder | Downloads",
        state_graph_summary="No pending workflow.",
        policy_summary="TextEdit is allowed; terminal write is blocked.",
    )

    call = client.calls[0]
    joined_messages = "\n".join(message["content"] for message in call["messages"])
    assert "Active: Finder | Downloads" in joined_messages
    assert "No pending workflow." in joined_messages
    assert "TextEdit is allowed" in joined_messages
    assert "WorkflowPlan JSON schema" in joined_messages
    assert call["response_format"]["type"] == "json_schema"
    assert plan.workflow_category == WorkflowCategory.DOCUMENT
    assert plan.steps[0].action.action_type == ActionType.OPEN_APP


def test_planner_stores_last_model_result_for_timing_metadata():
    client = FakeClient(
        plan_payload(
            steps=[
                workflow_step(
                    "step-1",
                    "open_app",
                    "TextEdit is active.",
                    {"app_name": "TextEdit"},
                )
            ]
        )
    )
    planner = WorkflowPlanner(client=client, settings=make_settings())

    planner.create_plan(
        normalized_input=normalize_input("Open TextEdit"),
        intent=classify_intent(normalize_input("Open TextEdit")),
        observation_context="Active: Finder | Downloads",
        state_graph_summary="No pending workflow.",
        policy_summary="TextEdit is allowed.",
    )

    assert planner.last_result is not None
    assert planner.last_result.latency_ms == 12
    assert planner.last_result.usage == {"total_tokens": 42}
    assert planner.last_result.time_info == {"total_time": 0.012}


def test_planner_caps_workflow_steps_to_settings_limit():
    steps = [
        workflow_step(f"step-{index}", "verify", f"Verification {index}.")
        for index in range(1, 7)
    ]
    client = FakeClient(plan_payload(steps=steps))

    plan = WorkflowPlanner(client=client, settings=make_settings(max_workflow_steps=3)).create_plan(
        normalized_input=normalize_input("Open TextEdit and write a title"),
        intent=classify_intent(normalize_input("Open TextEdit and write a title")),
        observation_context="Active: Finder | Downloads",
        state_graph_summary="No pending workflow.",
        policy_summary="TextEdit is allowed.",
    )

    assert [step.step_id for step in plan.steps] == ["step-1", "step-2", "step-3"]


def test_planner_accepts_answer_only_schema_valid_json():
    client = FakeClient(plan_payload(steps=[], category="answer", required=False))

    plan = WorkflowPlanner(client=client, settings=make_settings()).create_plan(
        normalized_input=normalize_input("What is on my screen?"),
        intent=classify_intent(normalize_input("What is on my screen?")),
        observation_context="Active: Preview | Hackathon PDF",
        state_graph_summary="No pending workflow.",
        policy_summary="Read-only answers are inform-only.",
    )

    assert plan.workflow_required is False
    assert plan.workflow_category == WorkflowCategory.ANSWER
    assert plan.approval_tier == ApprovalTier.INFORM_ONLY
    assert plan.steps == []


def test_planner_preserves_app_launch_verify_action_verify_pattern():
    steps = [
        workflow_step("step-1", "open_app", "TextEdit is active.", {"app_name": "TextEdit"}),
        workflow_step("step-2", "verify", "TextEdit active window is verified."),
        workflow_step("step-3", "type_text", "The title Cue is inserted.", {"text": "Cue"}),
        workflow_step("step-4", "verify", "The title Cue is visible."),
    ]
    client = FakeClient(plan_payload(steps=steps))

    plan = WorkflowPlanner(client=client, settings=make_settings()).create_plan(
        normalized_input=normalize_input("Open TextEdit and write a title"),
        intent=classify_intent(normalize_input("Open TextEdit and write a title")),
        observation_context="Active: Finder | Downloads",
        state_graph_summary="No pending workflow.",
        policy_summary="TextEdit is allowed.",
    )

    assert [step.action.action_type for step in plan.steps] == [
        ActionType.OPEN_APP,
        ActionType.VERIFY,
        ActionType.TYPE_TEXT,
        ActionType.VERIFY,
    ]
