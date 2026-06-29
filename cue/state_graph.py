"""Compact desktop state graph persisted between workflow steps."""

from __future__ import annotations

from dataclasses import dataclass, field
import json
from pathlib import Path
from typing import Any

from cue.context import DesktopObservation


@dataclass
class DesktopStateGraph:
    session_path: str | Path = ".cue/session.json"
    current_apps: list[dict[str, Any]] = field(default_factory=list)
    windows: list[dict[str, Any]] = field(default_factory=list)
    focused_element: dict[str, Any] = field(default_factory=dict)
    cursor: dict[str, Any] = field(default_factory=dict)
    pending_workflow_id: str | None = None
    completed_steps: list[str] = field(default_factory=list)
    cancelled_steps: list[str] = field(default_factory=list)
    last_verified_step: str | None = None
    last_observation_summary: str | None = None

    def update_from_observation(self, observation: DesktopObservation) -> None:
        self.current_apps = _copy_records(observation.apps)
        self.windows = _copy_records(observation.windows)
        self.focused_element = observation.focused_element.to_dict()
        self.cursor = observation.cursor_position.to_dict()
        self.last_observation_summary = observation.to_prompt_context(
            include_screenshot=False
        )

    def set_pending_workflow(self, workflow_id: str | None) -> None:
        self.pending_workflow_id = workflow_id

    def mark_step_completed(self, step_id: str) -> None:
        _append_once(self.completed_steps, step_id)

    def mark_step_cancelled(self, step_id: str) -> None:
        _append_once(self.cancelled_steps, step_id)

    def mark_step_verified(self, step_id: str) -> None:
        self.last_verified_step = step_id

    def to_dict(self) -> dict[str, Any]:
        return {
            "current_apps": self.current_apps,
            "windows": self.windows,
            "focused_element": self.focused_element,
            "cursor": self.cursor,
            "pending_workflow_id": self.pending_workflow_id,
            "completed_steps": self.completed_steps,
            "cancelled_steps": self.cancelled_steps,
            "last_verified_step": self.last_verified_step,
            "last_observation_summary": self.last_observation_summary,
        }

    def persist(self, path: str | Path | None = None) -> dict[str, Any]:
        target = Path(path or self.session_path)
        target.parent.mkdir(parents=True, exist_ok=True)
        record = self.to_dict()
        target.write_text(
            json.dumps(record, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        return record

    @classmethod
    def load(cls, path: str | Path = ".cue/session.json") -> "DesktopStateGraph":
        target = Path(path)
        record = json.loads(target.read_text(encoding="utf-8"))
        return cls(
            session_path=target,
            current_apps=record.get("current_apps", []),
            windows=record.get("windows", []),
            focused_element=record.get("focused_element", {}),
            cursor=record.get("cursor", {}),
            pending_workflow_id=record.get("pending_workflow_id"),
            completed_steps=record.get("completed_steps", []),
            cancelled_steps=record.get("cancelled_steps", []),
            last_verified_step=record.get("last_verified_step"),
            last_observation_summary=record.get("last_observation_summary"),
        )


def _copy_records(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [dict(record) for record in records]


def _append_once(values: list[str], value: str) -> None:
    if value not in values:
        values.append(value)

