import json

from cue.context import DesktopObservation
from cue.focus import CursorPosition, FocusedElement
from cue.memory import SessionMemory


def make_observation():
    return DesktopObservation(
        active_app="TextEdit",
        active_window="Untitled",
        focused_element=FocusedElement(
            status="known",
            role="AXTextArea",
            title="Document body",
            value="Cue draft with api_key=sk-secretsecretsecret",
            source="test",
        ),
        cursor_position=CursorPosition(status="known", x=10, y=20, source="test"),
        screenshot_ref="shot-secret-ref",
        sources=["test"],
    )


def test_redacted_memory_persists_preferences_and_workflow_state(tmp_path):
    path = tmp_path / ".cue" / "memory.json"
    memory = SessionMemory(path)

    record = memory.save_session(
        session_id="session-1",
        preferences={
            "speech_rate": "fast",
            "contact": "kartik@example.com",
            "api_key": "sk-secretsecretsecret",
        },
        observation=make_observation(),
        workflow_id="workflow-1",
        workflow_state="awaiting_step_approval",
        completed_steps=["step-1"],
        prompt_text="prompt: Please copy the whole private prompt into memory.",
        document_text="full_document_text: This full document should not persist.",
        screenshot_ref="raw://shot-secret-ref",
    )

    raw = path.read_text(encoding="utf-8")
    persisted = json.loads(raw)

    assert record == persisted
    assert persisted["session_id"] == "session-1"
    assert persisted["preferences"]["speech_rate"] == "fast"
    assert persisted["last_app"] == "TextEdit"
    assert persisted["last_window"] == "Untitled"
    assert persisted["workflow"]["workflow_id"] == "workflow-1"
    assert persisted["workflow"]["completed_steps"] == ["step-1"]
    assert "[REDACTED_EMAIL]" in raw
    assert "[REDACTED_API_KEY]" in raw
    assert "kartik@example.com" not in raw
    assert "sk-secretsecretsecret" not in raw
    assert "whole private prompt" not in raw
    assert "full document should not persist" not in raw

    loaded = memory.load()
    assert loaded == persisted


def test_memory_never_persists_screenshot_references_by_default(tmp_path):
    path = tmp_path / ".cue" / "memory.json"

    SessionMemory(path).save_session(
        session_id="session-1",
        preferences={},
        observation=make_observation(),
        workflow_id="workflow-1",
        workflow_state="preview_ready",
        completed_steps=[],
        screenshot_ref="shot-secret-ref",
    )

    raw = path.read_text(encoding="utf-8")

    assert "screenshot" not in raw.casefold()
    assert "shot-secret-ref" not in raw
