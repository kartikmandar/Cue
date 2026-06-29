import subprocess
from pathlib import Path

import pytest

from cue import demo


def completed_process(command):
    return subprocess.CompletedProcess(
        args=command,
        returncode=0,
        stdout="",
        stderr="",
    )


def test_demo_assets_are_repo_local_and_present():
    for target in demo.DEMO_TARGETS.values():
        if target.path is None:
            continue

        assert target.path.exists()
        assert demo.DEMO_ASSETS_DIR in target.path.parents


def test_open_helpers_use_only_safe_macos_open_targets(monkeypatch):
    commands = []

    def fake_run(command, capture_output, text, check, timeout):
        commands.append(command)
        return completed_process(command)

    monkeypatch.setattr("cue.demo.subprocess.run", fake_run)

    results = [
        demo.open_demo_form(),
        demo.open_dashboard(),
        demo.open_sample_brief(),
        demo.open_hackathon_pdf(),
        demo.open_textedit(),
        demo.open_terminal(),
    ]

    assert [result.ok for result in results] == [True, True, True, True, True, True]
    assert commands == [
        ["open", str(demo.INACCESSIBLE_FORM_PATH)],
        ["open", str(demo.LOCAL_DASHBOARD_PATH)],
        ["open", str(demo.SAMPLE_BRIEF_PATH)],
        ["open", str(demo.HACKATHON_PDF_PATH)],
        ["open", "-a", "TextEdit"],
        ["open", "-a", "Terminal"],
    ]


def test_open_terminal_has_no_command_execution_argument():
    with pytest.raises(TypeError):
        demo.open_terminal(command="echo unsafe")


def test_demo_runner_dry_run_does_not_open_apps(monkeypatch, capsys):
    def fail_if_called(*args, **kwargs):
        raise AssertionError("dry run must not call macOS open")

    monkeypatch.setattr("cue.demo.subprocess.run", fail_if_called)

    assert demo.main(["--dry-run"]) == 0

    output = capsys.readouterr().out
    assert "Dry run" in output
    assert "hackathon-pdf" in output
    assert "terminal" in output


def test_run_demo_script_uses_python_module_without_shell_command_surface():
    script = Path("scripts/run_demo.sh")

    assert script.exists()

    content = script.read_text(encoding="utf-8")
    assert "python -m cue.demo" in content
    assert "eval" not in content
    assert "sh -c" not in content
    assert "bash -c" not in content
    assert "osascript" not in content
