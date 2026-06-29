import subprocess

from cue.speech import speak


def test_speak_always_prints_text_when_disabled(capsys):
    calls = []

    speak("Cue narration", enabled=False, runner=lambda *args, **kwargs: calls.append((args, kwargs)))

    output = capsys.readouterr()
    assert output.out == "Cue narration\n"
    assert calls == []


def test_speak_calls_macos_say_with_stdin_when_enabled(capsys):
    calls = []

    def fake_runner(command, **kwargs):
        calls.append((command, kwargs))
        return subprocess.CompletedProcess(command, 0)

    speak("Cue narration", enabled=True, runner=fake_runner)

    output = capsys.readouterr()
    assert output.out == "Cue narration\n"
    assert calls[0][0] == ["say"]
    assert calls[0][1]["input"] == "Cue narration"
    assert calls[0][1]["text"] is True
    assert calls[0][1]["check"] is False


def test_speak_falls_back_to_printing_when_say_fails(capsys):
    def failing_runner(command, **kwargs):
        raise OSError("say is unavailable")

    speak("Cue narration", enabled=True, runner=failing_runner)

    output = capsys.readouterr()
    assert output.out == "Cue narration\n"
