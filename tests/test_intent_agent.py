import pytest

from cue.actions import WorkflowCategory
from cue.input_agent import InputAgent, normalize_input
from cue.intent_agent import IntentAgent, classify_intent


def test_normalize_input_collapses_whitespace_and_preserves_raw_text():
    result = normalize_input(
        "  Open   TextEdit\nand write a title  ",
        input_mode="speech",
        source="dictation",
    )

    assert result.raw_text == "  Open   TextEdit\nand write a title  "
    assert result.text == "Open TextEdit and write a title"
    assert result.input_mode == "speech"
    assert result.source == "dictation"


def test_normalize_input_rejects_empty_requests():
    with pytest.raises(ValueError, match="request text is required"):
        InputAgent().normalize("   ")


@pytest.mark.parametrize(
    ("request_text", "category"),
    [
        ("What is on my screen?", WorkflowCategory.ANSWER),
        ("Open TextEdit and write a title", WorkflowCategory.DOCUMENT),
        ("Open Terminal and start Claude Code", WorkflowCategory.CODING),
        ("Type the password", WorkflowCategory.SENSITIVE),
    ],
)
def test_intent_agent_classifies_task_6_sample_requests(request_text, category):
    intent = classify_intent(normalize_input(request_text))

    assert intent.workflow_category == category
    assert intent.intent == category.value


@pytest.mark.parametrize("request_text", ["Open Notes", "open the notes app"])
def test_intent_agent_treats_notes_launch_as_app_launch(request_text):
    intent = classify_intent(normalize_input(request_text))

    assert intent.workflow_category == WorkflowCategory.APP_LAUNCH
    assert intent.workflow_required is True


def test_intent_agent_marks_answer_only_requests_as_not_requiring_workflow():
    intent = IntentAgent().classify(normalize_input("What is on my screen?"))

    assert intent.workflow_required is False
    assert intent.risk_level == "none"
    assert intent.reason == "The user asked for a read-only answer."


def test_intent_agent_marks_password_typing_as_blocked_sensitive_workflow():
    intent = classify_intent(normalize_input("Type the password into the field"))

    assert intent.workflow_required is True
    assert intent.workflow_category == WorkflowCategory.SENSITIVE
    assert intent.risk_level == "blocked"
    assert "password" in intent.risk_reasons
