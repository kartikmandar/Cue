from cue.focus import (
    CursorPosition,
    FocusState,
    FocusedElement,
    get_focus_state,
    normalize_cursor_position,
    normalize_focused_element,
)


class FakeDriver:
    def __init__(self, window_state, focused_element=None, cursor_position=None):
        self.window_state = window_state
        self.focused_element = focused_element
        self.cursor_position = cursor_position

    def get_window_state(self):
        return self.window_state

    def get_focused_element(self):
        if isinstance(self.focused_element, Exception):
            raise self.focused_element
        return self.focused_element

    def get_cursor_position(self):
        if isinstance(self.cursor_position, Exception):
            raise self.cursor_position
        return self.cursor_position


def test_focus_state_normalizes_window_element_cursor_and_sources():
    driver = FakeDriver(
        {"active_app": "TextEdit", "window_title": "Untitled"},
        {
            "role": "AXTextArea",
            "title": "Document body",
            "value": "Cue",
            "source": "cua:get_focused_element",
        },
        {"x": 120.9, "y": 240.1, "source": "cua:get_cursor_position"},
    )

    state = get_focus_state(driver=driver)

    assert state == FocusState(
        active_app="TextEdit",
        window_title="Untitled",
        focused_element=FocusedElement(
            status="known",
            role="AXTextArea",
            title="Document body",
            value="Cue",
            source="cua:get_focused_element",
            reason=None,
        ),
        cursor_position=CursorPosition(
            status="known",
            x=120,
            y=240,
            source="cua:get_cursor_position",
            reason=None,
        ),
        sources=["cua:get_window_state", "cua:get_focused_element", "cua:get_cursor_position"],
    )


def test_focus_returns_explicit_unknowns_when_cua_cannot_report_details():
    state = get_focus_state(
        driver=FakeDriver(
            {"app_name": "Finder", "title": "Downloads"},
            focused_element=RuntimeError("focus permission denied"),
            cursor_position=None,
        )
    )

    assert state.active_app == "Finder"
    assert state.window_title == "Downloads"
    assert state.focused_element.status == "unknown"
    assert state.focused_element.role is None
    assert "focus permission denied" in state.focused_element.reason
    assert state.cursor_position.status == "unknown"
    assert state.cursor_position.x is None
    assert state.cursor_position.reason == "Cua did not provide cursor position."


def test_normalizers_accept_common_cua_shapes():
    element = normalize_focused_element(
        {
            "focused_element": {
                "role": "AXButton",
                "name": "Continue",
                "text": "Submit form",
            }
        }
    )
    cursor = normalize_cursor_position({"position": {"x": "12", "y": "34"}})

    assert element.status == "known"
    assert element.role == "AXButton"
    assert element.title == "Continue"
    assert element.value == "Submit form"
    assert cursor == CursorPosition(
        status="known",
        x=12,
        y=34,
        source="cua:get_cursor_position",
        reason=None,
    )

