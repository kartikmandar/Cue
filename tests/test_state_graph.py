import json

from cue.context import DesktopObservation
from cue.focus import CursorPosition, FocusedElement
from cue.state_graph import DesktopStateGraph


def make_observation():
    return DesktopObservation(
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
        windows=[{"app_name": "TextEdit", "title": "Untitled"}],
        accessibility_tree={"role": "AXWindow"},
        screen_size={"width": 1440, "height": 900},
        screenshot_ref="shot-should-not-persist",
        sources=["cua"],
    )


def test_state_graph_updates_from_observation_and_tracks_workflow_steps():
    graph = DesktopStateGraph()

    graph.update_from_observation(make_observation())
    graph.set_pending_workflow("workflow-1")
    graph.mark_step_completed("open-textedit")
    graph.mark_step_cancelled("format-heading")
    graph.mark_step_verified("open-textedit")

    assert graph.current_apps == [{"name": "TextEdit"}, {"name": "Finder"}]
    assert graph.windows == [{"app_name": "TextEdit", "title": "Untitled"}]
    assert graph.focused_element["role"] == "AXTextArea"
    assert graph.cursor == {"status": "known", "x": 100, "y": 200, "source": "cua:get_cursor_position"}
    assert graph.pending_workflow_id == "workflow-1"
    assert graph.completed_steps == ["open-textedit"]
    assert graph.cancelled_steps == ["format-heading"]
    assert graph.last_verified_step == "open-textedit"
    assert "TextEdit" in graph.last_observation_summary


def test_state_graph_persists_minimal_session_without_screenshot_reference(tmp_path):
    path = tmp_path / ".cue" / "session.json"
    graph = DesktopStateGraph(session_path=path)
    graph.update_from_observation(make_observation())
    graph.set_pending_workflow("workflow-1")
    graph.mark_step_completed("open-textedit")

    persisted = graph.persist()

    raw = path.read_text(encoding="utf-8")
    record = json.loads(raw)
    assert persisted == record
    assert record["pending_workflow_id"] == "workflow-1"
    assert record["completed_steps"] == ["open-textedit"]
    assert "screenshot_ref" not in record
    assert "accessibility_tree" not in record
    assert "shot-should-not-persist" not in raw

    loaded = DesktopStateGraph.load(path)
    assert loaded.pending_workflow_id == "workflow-1"
    assert loaded.current_apps == [{"name": "TextEdit"}, {"name": "Finder"}]

