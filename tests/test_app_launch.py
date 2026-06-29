import subprocess

from cue.app_launch import LaunchResult, activate_app, open_app, open_file, wait_for_window


class FakeDriver:
    def __init__(self, window_states=None):
        self.window_states = list(window_states or [])
        self.activated_apps = []

    def get_window_state(self):
        if self.window_states:
            return self.window_states.pop(0)
        return {}

    def activate_app(self, app_name):
        self.activated_apps.append(app_name)
        return {"ok": True, "app_name": app_name}


def completed_process(returncode=0, stdout="", stderr=""):
    return subprocess.CompletedProcess(
        args=["open"],
        returncode=returncode,
        stdout=stdout,
        stderr=stderr,
    )


def test_open_app_uses_macos_open_and_verifies_active_window(monkeypatch):
    commands = []

    def fake_run(command, capture_output, text, check, timeout):
        commands.append(command)
        return completed_process()

    monkeypatch.setattr("cue.app_launch.subprocess.run", fake_run)
    driver = FakeDriver(
        [{"active_app": "TextEdit", "window_title": "Untitled"}]
    )

    result = open_app("TextEdit", driver=driver)

    assert commands == [["open", "-a", "TextEdit"]]
    assert result == LaunchResult(
        ok=True,
        app_name="TextEdit",
        window_title="Untitled",
        reason="TextEdit active with window Untitled.",
    )


def test_open_app_returns_structured_failure_when_open_fails(monkeypatch):
    def fake_run(command, capture_output, text, check, timeout):
        return completed_process(returncode=1, stderr="Unable to find application")

    monkeypatch.setattr("cue.app_launch.subprocess.run", fake_run)

    result = open_app("MissingApp", driver=FakeDriver())

    assert result.ok is False
    assert result.app_name == "MissingApp"
    assert result.window_title is None
    assert "Unable to find application" in result.reason


def test_open_file_uses_macos_open_and_waits_for_file_window(monkeypatch, tmp_path):
    opened = []

    def fake_run(command, capture_output, text, check, timeout):
        opened.append(command)
        return completed_process()

    document = tmp_path / "brief.txt"
    document.write_text("Cue brief", encoding="utf-8")
    monkeypatch.setattr("cue.app_launch.subprocess.run", fake_run)
    driver = FakeDriver(
        [{"app_name": "TextEdit", "title": "brief.txt"}]
    )

    result = open_file(document, driver=driver)

    assert opened == [["open", str(document)]]
    assert result.ok is True
    assert result.app_name == "TextEdit"
    assert result.window_title == "brief.txt"


def test_activate_app_uses_cua_driver_then_verifies_focus():
    driver = FakeDriver(
        [{"active_app": "Finder", "active_window": {"title": "Downloads"}}]
    )

    result = activate_app("Finder", driver=driver)

    assert driver.activated_apps == ["Finder"]
    assert result.ok is True
    assert result.app_name == "Finder"
    assert result.window_title == "Downloads"


def test_wait_for_window_times_out_with_structured_result(monkeypatch):
    monkeypatch.setattr("cue.app_launch.time.sleep", lambda seconds: None)
    driver = FakeDriver(
        [
            {"active_app": "Finder", "window_title": "Downloads"},
            {"active_app": "Finder", "window_title": "Downloads"},
        ]
    )

    result = wait_for_window(
        title_hint="Untitled",
        app_name="TextEdit",
        timeout_seconds=0.01,
        poll_interval=0.01,
        driver=driver,
    )

    assert result.ok is False
    assert result.app_name == "TextEdit"
    assert result.window_title is None
    assert "Timed out" in result.reason
