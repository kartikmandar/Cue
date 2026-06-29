from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from cue.context import DesktopObservation
from cue.redaction import redact_for_persistence


class SessionMemory:
    def __init__(
        self,
        path: str | Path = ".cue/memory.json",
        *,
        save_screenshots: bool = False,
    ) -> None:
        self.path = Path(path)
        self.save_screenshots = save_screenshots

    def save_session(
        self,
        *,
        session_id: str,
        preferences: Mapping[str, Any],
        observation: DesktopObservation | Mapping[str, Any] | None,
        workflow_id: str | None,
        workflow_state: str,
        completed_steps: Sequence[str],
        prompt_text: str | None = None,
        document_text: str | None = None,
        screenshot_ref: str | None = None,
    ) -> dict[str, Any]:
        del prompt_text, document_text
        if not self.save_screenshots:
            screenshot_ref = None

        record = {
            "session_id": session_id,
            "preferences": _redact_value(dict(preferences)),
            "last_app": _redact_value(_observation_app(observation)),
            "last_window": _redact_value(_observation_window(observation)),
            "last_focus": _redact_value(_observation_focus(observation)),
            "workflow": {
                "workflow_id": workflow_id,
                "state": workflow_state,
                "completed_steps": list(completed_steps),
            },
        }
        if screenshot_ref and self.save_screenshots:
            record["screen_capture"] = "[REDACTED_RAW_CAPTURE]"

        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(
            json.dumps(record, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        return record

    def load(self) -> dict[str, Any]:
        if not self.path.exists():
            return {}
        return json.loads(self.path.read_text(encoding="utf-8"))


def _observation_app(
    observation: DesktopObservation | Mapping[str, Any] | None,
) -> str | None:
    if observation is None:
        return None
    if isinstance(observation, DesktopObservation):
        return observation.active_app
    return _first_text(observation.get("active_app"), observation.get("app"))


def _observation_window(
    observation: DesktopObservation | Mapping[str, Any] | None,
) -> str | None:
    if observation is None:
        return None
    if isinstance(observation, DesktopObservation):
        return observation.active_window
    return _first_text(
        observation.get("active_window"),
        observation.get("window"),
        observation.get("window_title"),
    )


def _observation_focus(
    observation: DesktopObservation | Mapping[str, Any] | None,
) -> dict[str, Any]:
    if observation is None:
        return {}
    if isinstance(observation, DesktopObservation):
        return observation.focused_element.to_dict()
    focus = observation.get("focused_element") or observation.get("focus") or {}
    return dict(focus) if isinstance(focus, Mapping) else {"value": str(focus)}


def _redact_value(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): _redact_value(item) for key, item in value.items()}
    if isinstance(value, list | tuple):
        return [_redact_value(item) for item in value]
    if isinstance(value, str):
        return redact_for_persistence(value)
    return value


def _first_text(*values: Any) -> str | None:
    for value in values:
        if value is None:
            continue
        text = str(value).strip()
        if text:
            return text
    return None
