from types import SimpleNamespace

from cue.actions import ActionType, WorkflowCategory
from cue.agent_models import IntentResult, NormalizedInput, WorkflowPlan
from cue.config import Settings
from cue.context import DesktopObservation
from cue.focus import CursorPosition, FocusedElement
from cue.model_planner import ModelBackedPlanner
from cue.policy import ApprovalTier


def make_settings(**overrides):
    values = {"cerebras_api_key": "test-key", "memory_enabled": False}
    values.update(overrides)
    return Settings(**values)


def make_observation():
    return DesktopObservation(
        active_app="Finder",
        active_window="Downloads",
        focused_element=FocusedElement(
            status="known",
            role="AXButton",
            title="Open",
            source="test",
        ),
        cursor_position=CursorPosition(status="known", x=10, y=20, source="test"),
        sources=["test"],
    )


def make_plan():
    normalized = NormalizedInput(
        text="Open TextEdit",
        raw_text="Open TextEdit",
        source="test",
    )
    intent = IntentResult(
        normalized_input=normalized,
        intent=WorkflowCategory.APP_LAUNCH.value,
        workflow_required=True,
        workflow_category=WorkflowCategory.APP_LAUNCH,
        risk_level="low",
        reason="test",
    )
    return WorkflowPlan(
        intent=intent,
        narration="Cue can open TextEdit.",
        workflow_required=True,
        workflow_category=WorkflowCategory.APP_LAUNCH,
        steps=[],
        risk_level="low",
        approval_tier=ApprovalTier.CONFIRM_EACH_ACTION,
        confirmation_prompt="Approve opening TextEdit?",
        expected_outcome="TextEdit is active.",
        risk_reasons=[],
        requires_reviewer_approval=False,
        redaction_applied=False,
        allowed_by_policy=True,
        policy_reason="Allowed for test.",
        audit_event_summary="Previewed.",
    )


class FakeWorkflowPlanner:
    def __init__(self):
        self.calls = []
        self.last_result = SimpleNamespace(
            provider="openrouter",
            model="google/gemma-4-31b-it:free",
            latency_ms=1080,
            usage={"total_tokens": 15},
            time_info={"service_tier": "default"},
        )

    def create_plan(
        self,
        *,
        normalized_input,
        intent,
        observation_context,
        state_graph_summary,
        policy_summary,
    ):
        self.calls.append(
            {
                "normalized_input": normalized_input,
                "intent": intent,
                "observation_context": observation_context,
                "state_graph_summary": state_graph_summary,
                "policy_summary": policy_summary,
            }
        )
        return make_plan()


def test_model_backed_planner_builds_prompt_context_and_exposes_last_result():
    workflow_planner = FakeWorkflowPlanner()
    planner = ModelBackedPlanner(
        settings=make_settings(),
        workflow_planner=workflow_planner,
    )

    plan = planner("Open TextEdit", make_observation())

    call = workflow_planner.calls[0]
    assert plan.workflow_category == WorkflowCategory.APP_LAUNCH
    assert call["normalized_input"].text == "Open TextEdit"
    assert call["intent"].workflow_category == WorkflowCategory.APP_LAUNCH
    assert "Active: Finder | Downloads" in call["observation_context"]
    assert "Allowed apps:" in call["policy_summary"]
    assert planner.last_result is workflow_planner.last_result


def test_model_backed_planner_uses_local_pdf_recipe_without_model_call():
    workflow_planner = FakeWorkflowPlanner()
    planner = ModelBackedPlanner(
        settings=make_settings(),
        workflow_planner=workflow_planner,
    )

    plan = planner("Open the hackathon PDF and summarize it.", make_observation())

    assert workflow_planner.calls == []
    assert plan.workflow_category == WorkflowCategory.PDF
    assert plan.steps[0].action.action_type == ActionType.OPEN_FILE
    assert (
        plan.steps[0]
        .action.payload["path"]
        .endswith("Gemma 4 Hackathon Instruction Document.pdf")
    )
    assert "judging tracks" in plan.steps[2].expected_outcome


def test_model_backed_planner_uses_terminal_handoff_recipe_that_types_prompt():
    workflow_planner = FakeWorkflowPlanner()
    planner = ModelBackedPlanner(
        settings=make_settings(),
        workflow_planner=workflow_planner,
    )

    plan = planner(
        "Open Terminal for this project and write a Claude Code prompt to inspect the repo.",
        make_observation(),
    )

    assert workflow_planner.calls == []
    assert plan.workflow_category == WorkflowCategory.CODING
    assert plan.approval_tier == ApprovalTier.CONFIRM_SENSITIVE
    type_steps = [
        step for step in plan.steps if step.action.action_type == ActionType.TYPE_TEXT
    ]
    assert len(type_steps) == 1
    assert "inspect this project read-only" in type_steps[0].action.payload["text"]
    assert "\n" not in type_steps[0].action.payload["text"]
    assert type_steps[0].action.payload["press_return"] is False
