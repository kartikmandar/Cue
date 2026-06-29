import json
import subprocess
from pathlib import Path
from unittest.mock import patch

import pytest

from cue.cua_driver import CuaDriver, CuaDriverError


def completed_process(stdout='{"ok": true}', stderr="", returncode=0):
    return subprocess.CompletedProcess(
        args=["cua-driver"],
        returncode=returncode,
        stdout=stdout,
        stderr=stderr,
    )


def command_payload(mock_run):
    command = mock_run.call_args.args[0]
    return command, json.loads(command[3])


def test_call_invokes_cua_driver_with_empty_payload_when_none():
    with patch("cue.cua_driver.subprocess.run") as run:
        run.return_value = completed_process('{"apps": ["Finder"]}')

        result = CuaDriver().call("list_apps")

    command, payload = command_payload(run)
    assert command[:3] == ["cua-driver", "call", "list_apps"]
    assert payload == {}
    assert result == {"apps": ["Finder"]}
    run.assert_called_once_with(
        ["cua-driver", "call", "list_apps", "{}"],
        capture_output=True,
        text=True,
        check=False,
        timeout=10,
    )


def test_observation_methods_send_expected_json_payloads():
    with patch("cue.cua_driver.subprocess.run") as run:
        run.return_value = completed_process()
        driver = CuaDriver()

        driver.list_apps()
        driver.list_windows()
        driver.get_screen_size()
        driver.get_window_state(pid=123, window_id=456)
        driver.get_focused_element()
        driver.get_cursor_position()
        driver.get_accessibility_tree()
        driver.get_accessibility_tree(window_id="window-123")

    calls = [call.args[0] for call in run.call_args_list]
    assert [(call[2], json.loads(call[3])) for call in calls] == [
        ("list_apps", {}),
        ("list_windows", {}),
        ("get_screen_size", {}),
        (
            "get_window_state",
            {
                "capture_mode": "ax",
                "max_depth": 10,
                "max_elements": 100,
                "pid": 123,
                "window_id": 456,
            },
        ),
        ("get_cursor_position", {}),
        ("get_accessibility_tree", {}),
        ("get_accessibility_tree", {}),
    ]


def test_get_window_state_selects_frontmost_window_with_ax_only_payload():
    with patch("cue.cua_driver.subprocess.run") as run:
        run.side_effect = [
            completed_process(
                json.dumps(
                    {
                        "windows": [
                            {
                                "pid": 111,
                                "window_id": 222,
                                "z_index": 1,
                                "is_on_screen": True,
                            },
                            {
                                "pid": 333,
                                "window_id": 444,
                                "z_index": 9,
                                "is_on_screen": True,
                            },
                        ]
                    }
                )
            ),
            completed_process('{"elements": []}'),
        ]

        result = CuaDriver().get_window_state()

    calls = [call.args[0] for call in run.call_args_list]
    assert result == {"elements": []}
    assert [(call[2], json.loads(call[3])) for call in calls] == [
        ("list_windows", {"on_screen_only": True}),
        (
            "get_window_state",
            {
                "capture_mode": "ax",
                "max_depth": 10,
                "max_elements": 100,
                "pid": 333,
                "window_id": 444,
            },
        ),
    ]


def test_get_focused_element_returns_explicit_unknown_without_driver_call():
    with patch("cue.cua_driver.subprocess.run") as run:
        result = CuaDriver().get_focused_element()

    assert result["status"] == "unknown"
    assert "standalone focused element" in result["reason"]
    run.assert_not_called()


def test_action_methods_send_expected_json_payloads():
    with patch("cue.cua_driver.subprocess.run") as run:
        run.return_value = completed_process()
        driver = CuaDriver()

        driver.open_app("TextEdit")
        driver.open_file(Path("/tmp/cue-demo.txt"))
        driver.activate_app("Finder")
        driver.click(120, 250)
        driver.type_text("Cue", pid=123, window_id=456)
        driver.hotkey(["command", "n"], pid=123, window_id=456)
        driver.press_key("escape", pid=123, window_id=456)
        driver.scroll("down", 3, pid=123, window_id=456)
        driver.set_value("1", "value", pid=123, window_id=456)
        driver.focus_element("element-2", pid=123, window_id=456)

    calls = [call.args[0] for call in run.call_args_list]
    assert [(call[2], json.loads(call[3])) for call in calls] == [
        ("launch_app", {"name": "TextEdit"}),
        ("launch_app", {"urls": ["/tmp/cue-demo.txt"]}),
        ("launch_app", {"name": "Finder"}),
        ("click", {"x": 120, "y": 250}),
        ("type_text", {"pid": 123, "text": "Cue", "window_id": 456}),
        ("hotkey", {"keys": ["command", "n"], "pid": 123, "window_id": 456}),
        ("press_key", {"key": "escape", "pid": 123, "window_id": 456}),
        ("scroll", {"amount": 3, "direction": "down", "pid": 123, "window_id": 456}),
        ("set_value", {"element_index": 1, "pid": 123, "value": "value", "window_id": 456}),
        ("focus_element", {"element_id": "element-2", "pid": 123, "window_id": 456}),
    ]


def test_nonzero_subprocess_exit_raises_cua_driver_error_with_diagnostics():
    with patch("cue.cua_driver.subprocess.run") as run:
        run.return_value = completed_process(
            stdout="partial output with sk-cb-1234567890abcdef",
            stderr="Accessibility permission missing",
            returncode=2,
        )

        with pytest.raises(CuaDriverError) as error:
            CuaDriver().call("list_apps")

    message = str(error.value)
    assert "list_apps" in message
    assert "exit code 2" in message
    assert "Accessibility permission missing" in message
    assert "[REDACTED_SECRET]" in message
    assert "sk-cb-1234567890abcdef" not in message


def test_invalid_json_subprocess_output_raises_cua_driver_error():
    with patch("cue.cua_driver.subprocess.run") as run:
        run.return_value = completed_process(
            stdout="not json",
            stderr="driver returned malformed output",
        )

        with pytest.raises(CuaDriverError) as error:
            CuaDriver().call("get_screen_size")

    message = str(error.value)
    assert "get_screen_size" in message
    assert "invalid JSON" in message
    assert "not json" in message
