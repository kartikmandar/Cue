import os
import json
import subprocess


def test_doctor_script_uses_current_cua_diagnostic_payloads(tmp_path):
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    log_path = tmp_path / "cua-driver-calls.log"
    stub = bin_dir / "cua-driver"
    stub.write_text(
        """#!/usr/bin/env bash
set -euo pipefail
printf '%s\\t%s\\t%s\\n' "${1:-}" "${2:-}" "${3:-}" >> "$CUA_DRIVER_STUB_LOG"

case "${1:-}" in
  doctor)
    printf 'doctor ok\\n'
    ;;
  call)
    tool="${2:-}"
    payload="${3:-}"
    case "$tool" in
      list_apps)
        [[ "$payload" == "{}" ]] || exit 42
        printf '{"apps":[]}\\n'
        ;;
      list_windows)
        [[ "$payload" == "{}" || "$payload" == '{"on_screen_only":true}' ]] || exit 42
        printf '{"windows":[{"pid":123,"window_id":456,"z_index":9,"is_on_screen":true,"on_current_space":true}]}\\n'
        ;;
      get_window_state)
        [[ "$payload" == *'"pid": 123'* && "$payload" == *'"window_id": 456'* && "$payload" == *'"capture_mode": "ax"'* ]] || exit 42
        printf '{"elements":[]}\\n'
        ;;
      get_screen_size)
        [[ "$payload" == "{}" ]] || exit 42
        printf '{"width":100,"height":100,"scale_factor":1}\\n'
        ;;
      get_accessibility_tree)
        [[ "$payload" == "{}" ]] || exit 42
        printf '{"apps":[],"windows":[]}\\n'
        ;;
      check_permissions)
        [[ "$payload" == '{"prompt":false}' ]] || exit 42
        printf '{"accessibility":true,"screen_recording":true}\\n'
        ;;
      get_cursor_position)
        [[ "$payload" == "{}" ]] || exit 42
        printf '{"x":1,"y":2}\\n'
        ;;
      get_focused_element)
        printf 'Unknown tool: get_focused_element\\n' >&2
        exit 64
        ;;
      *)
        printf 'unexpected tool: %s\\n' "$tool" >&2
        exit 64
        ;;
    esac
    ;;
  *)
    printf 'unexpected cua-driver args: %s\\n' "$*" >&2
    exit 64
    ;;
esac
""",
        encoding="utf-8",
    )
    stub.chmod(0o755)

    env = os.environ.copy()
    env["PATH"] = f"{bin_dir}{os.pathsep}{env['PATH']}"
    env["CUA_DRIVER_STUB_LOG"] = str(log_path)

    result = subprocess.run(
        ["bash", "scripts/doctor.sh"],
        text=True,
        capture_output=True,
        env=env,
        check=False,
    )

    assert result.returncode == 0, result.stderr + result.stdout
    records = [line.split("\t", 2) for line in log_path.read_text(encoding="utf-8").splitlines()]
    calls = [(parts[1], parts[2]) for parts in records if parts[0] == "call"]
    call_tools = [tool for tool, _payload in calls]

    assert "get_focused_element" not in call_tools
    assert ("list_apps", "{}") in calls
    assert ("list_windows", "{}") in calls
    assert ("list_windows", '{"on_screen_only":true}') in calls
    assert ("get_accessibility_tree", "{}") in calls
    assert ("check_permissions", '{"prompt":false}') in calls
    assert ("get_screen_size", "{}") in calls
    assert ("get_cursor_position", "{}") in calls

    window_payload = next(payload for tool, payload in calls if tool == "get_window_state")
    assert json.loads(window_payload) == {
        "pid": 123,
        "window_id": 456,
        "capture_mode": "ax",
        "max_elements": 100,
        "max_depth": 10,
    }
