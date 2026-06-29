from pathlib import Path


SMOKE_TEST_DOC = Path("scripts/manual_cua_smoke_test.md")

REQUIRED_COMMANDS = [
    "cua-driver doctor",
    "cua-driver call list_apps '{}'",
    "cua-driver call list_windows '{}'",
    "cua-driver call get_window_state '{}'",
    "cua-driver call get_screen_size '{}'",
    "cua-driver call get_focused_element '{}'",
    "cua-driver call get_cursor_position '{}'",
    "pixi run doctor",
]


def test_manual_cua_smoke_test_documents_required_diagnostics():
    content = SMOKE_TEST_DOC.read_text(encoding="utf-8")

    for command in REQUIRED_COMMANDS:
        assert command in content

    assert "JSON or clear driver diagnostics" in content
    assert "when supported" in content


def test_manual_cua_smoke_test_gates_safe_textedit_action():
    content = SMOKE_TEST_DOC.read_text(encoding="utf-8").lower()

    assert "textedit" in content
    assert "confirm focus" in content
    assert "explicit approval" in content
    assert "harmless word" in content
    assert "do not run task 16" in content
