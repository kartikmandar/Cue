from cue.context import DesktopObservation
from cue.focus import CursorPosition, FocusedElement


def test_desktop_observation_prompt_context_is_compact_and_blind_oriented():
    observation = DesktopObservation(
        active_app="TextEdit",
        active_window="Untitled",
        focused_element=FocusedElement(
            status="known",
            role="AXTextArea",
            title="Document body",
            value="Cue draft",
            source="cua:get_focused_element",
        ),
        cursor_position=CursorPosition(
            status="known",
            x=100,
            y=200,
            source="cua:get_cursor_position",
        ),
        apps=[{"name": "TextEdit"}, {"name": "Finder"}],
        windows=[
            {"app_name": "TextEdit", "title": "Untitled"},
            {"app_name": "Finder", "title": "Downloads"},
        ],
        accessibility_tree={"role": "AXWindow", "children": [{"title": "Body"}]},
        screen_size={"width": 1440, "height": 900},
        screenshot_ref="shot-123",
        sources=["cua:list_apps", "cua:list_windows", "cua:get_accessibility_tree"],
    )

    context = observation.to_prompt_context()

    assert "Active: TextEdit | Untitled" in context
    assert "Focus: AXTextArea 'Document body' value='Cue draft'" in context
    assert "Cursor: x=100 y=200" in context
    assert "Open apps: TextEdit, Finder" in context
    assert "Windows: TextEdit: Untitled; Finder: Downloads" in context
    assert "Screen: 1440x900" in context
    assert "Screenshot ref: shot-123" in context
    assert "Use this for blind workflow narration" in context
    assert len(context) < 900


def test_prompt_context_reports_unknown_focus_and_no_screenshot_clearly():
    observation = DesktopObservation(
        active_app=None,
        active_window=None,
        focused_element=FocusedElement.unknown("not supported"),
        cursor_position=CursorPosition.unknown("not supported"),
        apps=[],
        windows=[],
        accessibility_tree=None,
        screen_size=None,
        screenshot_ref=None,
        sources=[],
    )

    context = observation.to_prompt_context()

    assert "Active: unknown app | unknown window" in context
    assert "Focus: unknown (not supported)" in context
    assert "Cursor: unknown (not supported)" in context
    assert "Screenshot ref: none" in context

