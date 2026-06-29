"""Focus and cursor normalization helpers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from cue.cua_driver import CuaDriver


@dataclass(frozen=True)
class FocusedElement:
    status: str
    role: str | None = None
    title: str | None = None
    value: str | None = None
    source: str = "cua:get_focused_element"
    reason: str | None = None

    @classmethod
    def unknown(
        cls,
        reason: str,
        source: str = "cua:get_focused_element",
    ) -> "FocusedElement":
        return cls(status="unknown", source=source, reason=reason)

    def to_dict(self) -> dict[str, Any]:
        return _without_none(
            {
                "status": self.status,
                "role": self.role,
                "title": self.title,
                "value": self.value,
                "source": self.source,
                "reason": self.reason,
            }
        )


@dataclass(frozen=True)
class CursorPosition:
    status: str
    x: int | None = None
    y: int | None = None
    source: str = "cua:get_cursor_position"
    reason: str | None = None

    @classmethod
    def unknown(
        cls,
        reason: str,
        source: str = "cua:get_cursor_position",
    ) -> "CursorPosition":
        return cls(status="unknown", source=source, reason=reason)

    def to_dict(self) -> dict[str, Any]:
        return _without_none(
            {
                "status": self.status,
                "x": self.x,
                "y": self.y,
                "source": self.source,
                "reason": self.reason,
            }
        )


@dataclass(frozen=True)
class FocusState:
    active_app: str | None
    window_title: str | None
    focused_element: FocusedElement
    cursor_position: CursorPosition
    sources: list[str]

    def to_dict(self) -> dict[str, Any]:
        return {
            "active_app": self.active_app,
            "window_title": self.window_title,
            "focused_element": self.focused_element.to_dict(),
            "cursor_position": self.cursor_position.to_dict(),
            "sources": list(self.sources),
        }


def get_focus_state(driver: CuaDriver | None = None) -> FocusState:
    cua = driver or CuaDriver()
    sources = ["cua:get_window_state"]

    try:
        window_state = cua.get_window_state()
    except Exception as exc:  # pragma: no cover - defensive adapter boundary
        window_state = {}
        window_error = str(exc)
    else:
        window_error = None

    active_app, window_title = normalize_active_window(window_state)

    try:
        element = normalize_focused_element(cua.get_focused_element())
    except Exception as exc:
        element = FocusedElement.unknown(str(exc))
    sources.append(element.source)

    try:
        cursor = normalize_cursor_position(cua.get_cursor_position())
    except Exception as exc:
        cursor = CursorPosition.unknown(str(exc))
    sources.append(cursor.source)

    if window_error and element.status == "unknown" and cursor.status == "unknown":
        sources.append(f"cua:get_window_state error: {window_error}")

    return FocusState(
        active_app=active_app,
        window_title=window_title,
        focused_element=element,
        cursor_position=cursor,
        sources=sources,
    )


def normalize_active_window(window_state: dict[str, Any] | None) -> tuple[str | None, str | None]:
    state = window_state or {}
    active_window = _first_mapping(
        state.get("active_window"),
        state.get("window"),
        state.get("focused_window"),
    )

    app = _first_text(
        state.get("active_app"),
        state.get("app_name"),
        state.get("app"),
        state.get("application"),
        active_window.get("active_app") if active_window else None,
        active_window.get("app_name") if active_window else None,
        active_window.get("app") if active_window else None,
        active_window.get("owner") if active_window else None,
    )
    title = _first_text(
        state.get("window_title"),
        state.get("title"),
        state.get("name"),
        active_window.get("window_title") if active_window else None,
        active_window.get("title") if active_window else None,
        active_window.get("name") if active_window else None,
    )
    return app, title


def normalize_focused_element(raw: dict[str, Any] | None) -> FocusedElement:
    if not raw:
        return FocusedElement.unknown("Cua did not provide focused element.")
    if raw.get("status") == "unknown":
        return FocusedElement.unknown(
            _first_text(raw.get("reason")) or "Cua did not provide focused element.",
            source=_first_text(raw.get("source")) or "cua:get_window_state",
        )

    element = _first_mapping(raw.get("focused_element"), raw.get("element")) or raw
    role = _first_text(element.get("role"), element.get("ax_role"), element.get("type"))
    title = _first_text(
        element.get("title"),
        element.get("name"),
        element.get("label"),
        element.get("description"),
    )
    value = _first_text(
        element.get("value"),
        element.get("text"),
        element.get("content"),
        element.get("string_value"),
    )
    source = _first_text(raw.get("source"), element.get("source")) or "cua:get_focused_element"

    if role is None and title is None and value is None:
        return FocusedElement.unknown("Cua did not provide focused element.", source=source)

    return FocusedElement(
        status="known",
        role=role,
        title=title,
        value=value,
        source=source,
    )


def normalize_cursor_position(raw: dict[str, Any] | None) -> CursorPosition:
    if not raw:
        return CursorPosition.unknown("Cua did not provide cursor position.")

    position = _first_mapping(raw.get("position"), raw.get("cursor")) or raw
    x = _int_or_none(position.get("x"))
    y = _int_or_none(position.get("y"))
    source = _first_text(raw.get("source"), position.get("source")) or "cua:get_cursor_position"

    if x is None or y is None:
        return CursorPosition.unknown("Cua did not provide cursor position.", source=source)

    return CursorPosition(status="known", x=x, y=y, source=source)


def _without_none(values: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in values.items() if value is not None}


def _first_mapping(*values: Any) -> dict[str, Any] | None:
    for value in values:
        if isinstance(value, dict):
            return value
    return None


def _first_text(*values: Any) -> str | None:
    for value in values:
        if value is None:
            continue
        text = str(value).strip()
        if text:
            return text
    return None


def _int_or_none(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return None
