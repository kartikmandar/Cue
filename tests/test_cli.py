from cue.actions import ActionType, CueAction, WorkflowCategory
from cue.agent_models import (
    IntentResult,
    NormalizedInput,
    WorkflowPlan,
    WorkflowStep,
)
from cue.cli import LocalCliPlanner, main
from cue.config import Settings
from cue.context import DesktopObservation
from cue.focus import CursorPosition, FocusedElement
from cue.policy import ApprovalTier


class FakeExecutor:
    def __init__(self):
        self.calls = []

    def __call__(self, action):
        self.calls.append(action)
        return {"ok": True}


def make_settings(**overrides):
    values = {
        "cerebras_api_key": "test-key",
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
        cursor_position=CursorPosition(status="known", x=12, y=34, source="test"),
        sources=["test"],
    )


def make_intent(
    text,
    *,
    category=WorkflowCategory.ANSWER,
    workflow_required=False,
):
    normalized = NormalizedInput(
        text=text,
        raw_text=text,
        input_mode="text",
        source="cli",
    )
    return IntentResult(
        normalized_input=normalized,
        intent=category.value,
        workflow_required=workflow_required,
        workflow_category=category,
        risk_level="none" if not workflow_required else "low",
        reason="test intent",
    )


def answer_plan(request, observation):
    del observation
    return WorkflowPlan(
        intent=make_intent(request),
        narration="Cue can answer this from the current desktop state.",
        workflow_required=False,
        workflow_category=WorkflowCategory.ANSWER,
        steps=[],
        risk_level="none",
        approval_tier=ApprovalTier.INFORM_ONLY,
        confirmation_prompt="No approval is needed for a read-only answer.",
        expected_outcome="Current app and focus are narrated.",
        risk_reasons=[],
        requires_reviewer_approval=False,
        redaction_applied=False,
        allowed_by_policy=True,
        policy_reason="Read-only status request.",
        audit_event_summary="Read-only CLI preview.",
        workflow_id="workflow-readonly",
    )


def open_textedit_plan(request, observation):
    del observation
    open_step = WorkflowStep(
        step_id="step-1",
        title="Open TextEdit",
        action=CueAction(
            action_type=ActionType.OPEN_APP,
            payload={"app_name": "TextEdit"},
            reason="Open TextEdit for the approved workflow.",
            expected_app="TextEdit",
            changes_state=True,
        ),
        expected_outcome="TextEdit is active.",
        verification_criteria="The active app is TextEdit.",
    )
    verify_step = WorkflowStep(
        step_id="step-2",
        title="Verify TextEdit",
        action=CueAction(
            action_type=ActionType.VERIFY,
            payload={},
            reason="Verify that TextEdit is active before continuing.",
            expected_app="TextEdit",
            changes_state=False,
        ),
        expected_outcome="TextEdit remains active.",
        verification_criteria="The active app is TextEdit.",
    )
    return WorkflowPlan(
        intent=make_intent(
            request,
            category=WorkflowCategory.APP_LAUNCH,
            workflow_required=True,
        ),
        narration="Cue can open TextEdit after approval.",
        workflow_required=True,
        workflow_category=WorkflowCategory.APP_LAUNCH,
        steps=[open_step, verify_step],
        risk_level="low",
        approval_tier=ApprovalTier.CONFIRM_EACH_ACTION,
        confirmation_prompt="Approve opening TextEdit?",
        expected_outcome="TextEdit opens.",
        risk_reasons=[],
        requires_reviewer_approval=False,
        redaction_applied=False,
        allowed_by_policy=True,
        policy_reason="TextEdit is allowlisted.",
        audit_event_summary="Open TextEdit preview.",
        workflow_id="workflow-open",
    )


def test_cli_prints_read_only_workflow_status_and_narration(capsys):
    result = main(
        ["What app am I in and where is my focus?", "--no-speak"],
        settings=make_settings(),
        observer=lambda: make_observation(),
        planner=answer_plan,
    )

    output = capsys.readouterr().out
    assert result == 0
    assert "Active app: TextEdit" in output
    assert "Active window: Untitled" in output
    assert "Focus: AXTextArea Document body" in output
    assert "Policy tier: inform_only" in output
    assert "Workflow plan: No desktop action is needed." in output
    assert "Verification: not_run" in output
    assert "Narration:" in output
    assert "Current screen: TextEdit" in output


def test_cli_voice_mode_disabled_returns_clear_message(capsys):
    result = main(
        ["--input-mode", "voice"],
        settings=make_settings(enable_voice_input=False),
        observer=lambda: make_observation(),
        planner=answer_plan,
    )

    output = capsys.readouterr().out
    assert result == 2
    assert "Voice input is disabled" in output
    assert "CUE_ENABLE_VOICE_INPUT=true" in output


def test_local_cli_planner_opens_notes_app_for_notes_launch_request():
    settings = make_settings(
        allowed_apps=["TextEdit", "Finder", "Safari", "Terminal", "Notes"]
    )
    planner = LocalCliPlanner(settings=settings)

    plan = planner(
        "open the notes app",
        make_observation(app="CueApp", window="Cue", focus="Cue request"),
    )

    assert plan.workflow_category == WorkflowCategory.APP_LAUNCH
    assert plan.steps[0].action.action_type == ActionType.OPEN_APP
    assert plan.steps[0].action.payload == {"app_name": "Notes"}
    assert plan.steps[0].action.expected_app == "Notes"


def test_cli_next_without_approval_does_not_execute_state_changing_step(capsys):
    executor = FakeExecutor()

    result = main(
        ["Open TextEdit", "--next", "--no-speak"],
        settings=make_settings(),
        observer=lambda: make_observation(),
        planner=open_textedit_plan,
        executor=executor,
    )

    output = capsys.readouterr().out
    assert result == 0
    assert executor.calls == []
    assert "Next step was not executed because approval is required." in output
    assert "Policy tier: confirm_each_action" in output


def test_cli_read_only_flag_prevents_execution_even_with_approval(capsys):
    executor = FakeExecutor()

    result = main(
        ["Open TextEdit", "--approve", "--next", "--read-only", "--no-speak"],
        settings=make_settings(),
        observer=lambda: make_observation(),
        planner=open_textedit_plan,
        executor=executor,
    )

    output = capsys.readouterr().out
    assert result == 0
    assert executor.calls == []
    assert "Read-only mode prevented execution of the next step." in output
    assert "State: awaiting_step_approval" in output


def test_local_cli_planner_extracts_capitalized_document_text():
    plan = LocalCliPlanner(settings=make_settings())(
        "Write Cue as the title",
        make_observation(),
    )

    assert plan.steps[0].action.action_type == ActionType.TYPE_TEXT
    assert plan.steps[0].action.payload["text"] == "Cue as the title"


def test_local_cli_planner_uses_textedit_document_recipe_for_task_16_prompt():
    plan = LocalCliPlanner(settings=make_settings())(
        "Open TextEdit and type the project name Cue as a title, then put the cursor below it.",
        make_observation(app="Finder", window="Downloads", focus="Sidebar"),
    )

    assert [step.action.action_type for step in plan.steps] == [
        ActionType.OPEN_APP,
        ActionType.VERIFY,
        ActionType.TYPE_TEXT,
        ActionType.VERIFY,
    ]
    assert plan.steps[0].action.payload == {"app_name": "TextEdit"}
    assert plan.steps[2].action.payload == {"text": "Cue\n\n"}
    assert "cursor below" in plan.steps[2].expected_outcome.casefold()
    assert plan.confirmation_prompt.startswith("Approve opening TextEdit")
