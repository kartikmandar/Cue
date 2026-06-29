import pytest
from pydantic import ValidationError

from cue.actions import ActionType, CueAction, WorkflowCategory


def test_action_type_values_match_task_6_plan():
    assert [action.value for action in ActionType] == [
        "none",
        "open_app",
        "open_file",
        "activate_app",
        "click",
        "type_text",
        "hotkey",
        "press_key",
        "scroll",
        "set_value",
        "focus_element",
        "wait_for_window",
        "ask_confirmation",
        "request_reviewer_approval",
        "verify",
        "cancel_workflow",
    ]


def test_workflow_category_values_match_task_6_plan():
    assert [category.value for category in WorkflowCategory] == [
        "answer",
        "desktop",
        "app_launch",
        "document",
        "browser",
        "pdf",
        "terminal",
        "coding",
        "sensitive",
        "none",
    ]


def test_cue_action_carries_payload_reason_expectations_and_state_change_flag():
    action = CueAction(
        action_type=ActionType.TYPE_TEXT,
        payload={"text": "Cue"},
        reason="Write the approved title.",
        expected_app="TextEdit",
        expected_window="Untitled",
        expected_focus="document body",
        changes_state=True,
    )

    assert action.action_type == ActionType.TYPE_TEXT
    assert action.payload == {"text": "Cue"}
    assert action.reason == "Write the approved title."
    assert action.expected_app == "TextEdit"
    assert action.expected_window == "Untitled"
    assert action.expected_focus == "document body"
    assert action.changes_state is True


def test_cue_action_rejects_unsupported_action_type():
    with pytest.raises(ValidationError):
        CueAction(
            action_type="run_command",
            reason="Arbitrary shell execution is not a supported action.",
        )
