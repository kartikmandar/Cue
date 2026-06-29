from pathlib import Path


SMOKE_TEST_DOC = Path("scripts/manual_cua_smoke_test.md")

REQUIRED_COMMANDS = [
    "cua-driver doctor",
    "cua-driver call check_permissions '{\"prompt\":false}'",
    "cua-driver call list_apps '{}'",
    "cua-driver call list_windows '{}'",
    "cua-driver call list_windows '{\"on_screen_only\":true}'",
    "cua-driver call get_accessibility_tree '{}'",
    "cua-driver call get_window_state '{\"pid\":123,\"window_id\":456,\"capture_mode\":\"ax\",\"max_elements\":100,\"max_depth\":10}'",
    "cua-driver call get_screen_size '{}'",
    "cua-driver call get_cursor_position '{}'",
    "pixi run doctor",
]


def test_manual_cua_smoke_test_documents_required_diagnostics():
    content = SMOKE_TEST_DOC.read_text(encoding="utf-8")

    for command in REQUIRED_COMMANDS:
        assert command in content

    assert "JSON or clear driver diagnostics" in content
    assert "when supported" in content
    assert "get_focused_element" not in content


def test_manual_cua_smoke_test_gates_safe_textedit_action():
    content = SMOKE_TEST_DOC.read_text(encoding="utf-8").lower()

    assert "textedit" in content
    assert "confirm focus" in content
    assert "explicit approval" in content
    assert "harmless word" in content
    assert "do not run task 16" in content
