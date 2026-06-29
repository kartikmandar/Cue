from cue.actions import ActionType, CueAction
from cue.agent_models import WorkflowStep
from cue.context import DesktopObservation
from cue.focus import CursorPosition, FocusedElement
from cue.verifier import Verifier


class FakeObserver:
    def __init__(self, observation):
        self.observation = observation
        self.calls = 0

    def __call__(self):
        self.calls += 1
        return self.observation


def make_observation(
    *,
    app="TextEdit",
    window="Untitled",
    focus_title="Document body",
    focus_value="Cue",
):
    return DesktopObservation(
        active_app=app,
        active_window=window,
        focused_element=FocusedElement(
            status="known",
            role="AXTextArea",
            title=focus_title,
            value=focus_value,
            source="test",
        ),
        cursor_position=CursorPosition(status="known", x=120, y=240, source="test"),
        windows=[{"app_name": app, "title": window}],
        sources=["test"],
    )


def make_textedit_step(expected_text="Cue"):
    return WorkflowStep(
        step_id="step-1",
        title="Type title",
        action=CueAction(
            action_type=ActionType.TYPE_TEXT,
            payload={"text": expected_text},
            reason="Write the requested title.",
            expected_app="TextEdit",
            expected_window="Untitled",
            expected_focus="Document body",
            changes_state=True,
        ),
        expected_outcome=f"{expected_text} is visible in TextEdit.",
        verification_criteria=f"TextEdit shows {expected_text}.",
    )


def test_textedit_success_verification_reobserves_and_matches_expected_state():
    observer = FakeObserver(make_observation())

    result = Verifier(observer).verify_step(make_textedit_step())

    assert observer.calls == 1
    assert result.status == "passed"
    assert "TextEdit" in result.expected
    assert "TextEdit" in result.actual
    assert result.next_recommendation == "Continue to the next approved step."


def test_verification_fails_when_expected_text_is_not_visible():
    observer = FakeObserver(make_observation(focus_value="Draft"))

    result = Verifier(observer).verify_step(make_textedit_step())

    assert result.status == "failed"
    assert "text" in result.reason.casefold()
    assert "Cue" in result.expected
    assert "Draft" in result.actual
    assert result.next_recommendation == "Pause, narrate the mismatch, and re-observe before retrying."


def test_verification_is_unknown_without_expected_state():
    observer = FakeObserver(make_observation())
    step = WorkflowStep(
        step_id="step-0",
        title="Explain screen",
        action=CueAction(
            action_type=ActionType.NONE,
            payload={},
            reason="Answer without changing state.",
        ),
        expected_outcome="The screen is explained.",
    )

    result = Verifier(observer).verify_step(step)

    assert result.status == "unknown"
    assert "No concrete expected state" in result.reason
