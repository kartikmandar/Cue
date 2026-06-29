"""Desktop observation model for blind-first workflow prompts."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from cue.focus import CursorPosition, FocusedElement


@dataclass(frozen=True)
class DesktopObservation:
    active_app: str | None
    active_window: str | None
    focused_element: FocusedElement
    cursor_position: CursorPosition
    apps: list[dict[str, Any]] = field(default_factory=list)
    windows: list[dict[str, Any]] = field(default_factory=list)
    accessibility_tree: dict[str, Any] | None = None
    screen_size: dict[str, Any] | None = None
    screenshot_ref: str | None = None
    sources: list[str] = field(default_factory=list)

    def to_prompt_context(self, *, include_screenshot: bool = True) -> str:
        lines = [
            f"Active: {self.active_app or 'unknown app'} | "
            f"{self.active_window or 'unknown window'}",
            f"Focus: {_format_focus(self.focused_element)}",
            f"Cursor: {_format_cursor(self.cursor_position)}",
            f"Open apps: {_format_apps(self.apps)}",
            f"Windows: {_format_windows(self.windows)}",
            f"Screen: {_format_screen(self.screen_size)}",
            f"AX tree: {_format_tree(self.accessibility_tree)}",
        ]
        if include_screenshot:
            lines.append(f"Screenshot ref: {self.screenshot_ref or 'none'}")
        lines.extend(
            [
                f"Sources: {_format_sources(self.sources)}",
                "Use this for blind workflow narration and verify "
                "app/window/focus before acting.",
            ]
        )
        return "\n".join(lines)


def _format_focus(element: FocusedElement) -> str:
    if element.status != "known":
        reason = f" ({element.reason})" if element.reason else ""
        return f"unknown{reason}"

    label = element.role or "element"
    if element.title:
        label = f"{label} {element.title!r}"
    if element.value:
        label = f"{label} value={_clip(element.value)!r}"
    return label


def _format_cursor(cursor: CursorPosition) -> str:
    if cursor.status != "known":
        reason = f" ({cursor.reason})" if cursor.reason else ""
        return f"unknown{reason}"
    return f"x={cursor.x} y={cursor.y}"


def _format_apps(apps: list[dict[str, Any]]) -> str:
    names = [_first_text(app.get("name"), app.get("app_name"), app.get("title")) for app in apps]
    names = [name for name in names if name]
    return ", ".join(names[:8]) if names else "none"


def _format_windows(windows: list[dict[str, Any]]) -> str:
    summaries = []
    for window in windows[:8]:
        app = _first_text(window.get("app_name"), window.get("app"), window.get("owner"))
        title = _first_text(window.get("title"), window.get("window_title"), window.get("name"))
        if app and title:
            summaries.append(f"{app}: {title}")
        elif title:
            summaries.append(title)
    return "; ".join(summaries) if summaries else "none"


def _format_screen(screen_size: dict[str, Any] | None) -> str:
    if not screen_size:
        return "unknown"
    width = screen_size.get("width")
    height = screen_size.get("height")
    if width is None or height is None:
        return "unknown"
    return f"{width}x{height}"


def _format_tree(accessibility_tree: dict[str, Any] | None) -> str:
    if not accessibility_tree:
        return "none"
    role = _first_text(accessibility_tree.get("role"), accessibility_tree.get("type"))
    children = accessibility_tree.get("children")
    count = len(children) if isinstance(children, list) else 0
    if role:
        return f"available role={role} children={count}"
    return "available"


def _format_sources(sources: list[str]) -> str:
    return ", ".join(sources) if sources else "none"


def _first_text(*values: Any) -> str | None:
    for value in values:
        if value is None:
            continue
        text = str(value).strip()
        if text:
            return text
    return None


def _clip(value: str, limit: int = 80) -> str:
    if len(value) <= limit:
        return value
    return f"{value[:limit]}..."

