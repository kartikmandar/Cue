"""Low-level Cua Driver adapter."""

from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path
from typing import Any


class CuaDriverError(RuntimeError):
    """Raised when Cua Driver cannot complete a requested call."""


class CuaDriver:
    """Typed wrapper around Cua Driver CLI calls."""

    def __init__(self, executable: str = "cua-driver", timeout: int = 10) -> None:
        self.executable = executable
        self.timeout = timeout

    def call(self, tool: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        payload_json = json.dumps(payload or {}, sort_keys=True)
        command = [self.executable, "call", tool, payload_json]

        try:
            result = subprocess.run(
                command,
                capture_output=True,
                text=True,
                check=False,
                timeout=self.timeout,
            )
        except FileNotFoundError as exc:
            raise CuaDriverError(
                f"Cua Driver executable not found: {self.executable!r}. "
                "Run `pixi run install-cua` and then `pixi run doctor`."
            ) from exc
        except subprocess.TimeoutExpired as exc:
            diagnostics = _diagnostics(stdout=exc.stdout, stderr=exc.stderr)
            raise CuaDriverError(
                f"Cua Driver call {tool!r} timed out after {self.timeout}s. "
                f"{diagnostics}"
            ) from exc

        if result.returncode != 0:
            diagnostics = _diagnostics(stdout=result.stdout, stderr=result.stderr)
            raise CuaDriverError(
                f"Cua Driver call {tool!r} failed with exit code "
                f"{result.returncode}. {diagnostics}"
            )

        try:
            decoded = json.loads(result.stdout)
        except json.JSONDecodeError as exc:
            diagnostics = _diagnostics(stdout=result.stdout, stderr=result.stderr)
            raise CuaDriverError(
                f"Cua Driver call {tool!r} returned invalid JSON. {diagnostics}"
            ) from exc

        if not isinstance(decoded, dict):
            raise CuaDriverError(
                f"Cua Driver call {tool!r} returned JSON {type(decoded).__name__}, "
                "expected object."
            )
        return decoded

    def list_apps(self) -> dict[str, Any]:
        return self.call("list_apps")

    def list_windows(
        self,
        *,
        on_screen_only: bool | None = None,
        pid: int | None = None,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {}
        if on_screen_only is not None:
            payload["on_screen_only"] = on_screen_only
        if pid is not None:
            payload["pid"] = pid
        return self.call("list_windows", payload or None)

    def get_screen_size(self) -> dict[str, Any]:
        return self.call("get_screen_size")

    def get_window_state(
        self,
        *,
        pid: int | None = None,
        window_id: int | None = None,
        capture_mode: str = "ax",
        max_elements: int = 100,
        max_depth: int = 10,
    ) -> dict[str, Any]:
        target = (
            {"pid": pid, "window_id": window_id}
            if pid is not None and window_id is not None
            else self._frontmost_window()
        )
        payload = {
            "pid": int(target["pid"]),
            "window_id": int(target["window_id"]),
            "capture_mode": capture_mode,
            "max_elements": max_elements,
            "max_depth": max_depth,
        }
        return self.call("get_window_state", payload)

    def get_focused_element(self) -> dict[str, Any]:
        return {
            "status": "unknown",
            "reason": (
                "Cua Driver 0.6.8 does not expose a standalone focused element "
                "tool; focus must be inferred from the AX window state."
            ),
            "source": "cua:get_window_state",
        }

    def get_cursor_position(self) -> dict[str, Any]:
        return self.call("get_cursor_position")

    def get_accessibility_tree(
        self, window_id: str | None = None
    ) -> dict[str, Any]:
        del window_id
        return self.call("get_accessibility_tree")

    def open_app(self, app_name: str) -> dict[str, Any]:
        return self.call("launch_app", {"name": app_name})

    def open_file(self, path: str | Path) -> dict[str, Any]:
        return self.call("launch_app", {"urls": [str(path)]})

    def activate_app(self, app_name: str) -> dict[str, Any]:
        return self.call("launch_app", {"name": app_name})

    def click(self, x: int, y: int) -> dict[str, Any]:
        return self.call("click", {"x": x, "y": y})

    def type_text(
        self,
        text: str,
        *,
        pid: int | None = None,
        window_id: int | None = None,
    ) -> dict[str, Any]:
        return self.call(
            "type_text",
            self._target_payload({"text": text}, pid=pid, window_id=window_id),
        )

    def hotkey(
        self,
        keys: list[str],
        *,
        pid: int | None = None,
        window_id: int | None = None,
    ) -> dict[str, Any]:
        return self.call(
            "hotkey",
            self._target_payload({"keys": keys}, pid=pid, window_id=window_id),
        )

    def press_key(
        self,
        key: str,
        *,
        pid: int | None = None,
        window_id: int | None = None,
    ) -> dict[str, Any]:
        return self.call(
            "press_key",
            self._target_payload({"key": key}, pid=pid, window_id=window_id),
        )

    def scroll(
        self,
        direction: str,
        amount: int,
        *,
        pid: int | None = None,
        window_id: int | None = None,
    ) -> dict[str, Any]:
        return self.call(
            "scroll",
            self._target_payload(
                {"direction": direction, "amount": amount},
                pid=pid,
                window_id=window_id,
            ),
        )

    def set_value(
        self,
        element_id: str,
        value: str,
        *,
        pid: int | None = None,
        window_id: int | None = None,
    ) -> dict[str, Any]:
        payload = {"element_id": element_id, "value": value}
        if str(element_id).isdigit():
            payload = {"element_index": int(element_id), "value": value}
        return self.call(
            "set_value",
            self._target_payload(payload, pid=pid, window_id=window_id),
        )

    def focus_element(
        self,
        element_id: str,
        *,
        pid: int | None = None,
        window_id: int | None = None,
    ) -> dict[str, Any]:
        return self.call(
            "focus_element",
            self._target_payload(
                {"element_id": element_id},
                pid=pid,
                window_id=window_id,
            ),
        )

    def _target_payload(
        self,
        payload: dict[str, Any],
        *,
        pid: int | None = None,
        window_id: int | None = None,
    ) -> dict[str, Any]:
        if "pid" in payload:
            return payload
        target = (
            {"pid": pid, "window_id": window_id}
            if pid is not None and window_id is not None
            else self._frontmost_window()
        )
        return {
            **payload,
            "pid": int(target["pid"]),
            "window_id": int(target["window_id"]),
        }

    def _frontmost_window(self, app_name: str | None = None) -> dict[str, Any]:
        windows = self.list_windows(on_screen_only=True).get("windows", [])
        candidates = [
            window
            for window in windows
            if isinstance(window, dict)
            and window.get("pid") is not None
            and window.get("window_id") is not None
            and (
                app_name is None
                or _same_text(window.get("app_name"), app_name)
                or _same_text(window.get("app"), app_name)
            )
        ]
        if not candidates:
            raise CuaDriverError("Cua Driver did not report an on-screen target window.")
        return max(candidates, key=lambda window: int(window.get("z_index") or 0))


_SECRET_RE = re.compile(
    r"\b(?:sk|pk|cb|ck|ghp|gho|xox[baprs])[-_]"
    r"[A-Za-z0-9][A-Za-z0-9._-]{8,}\b"
    r"|"
    r"\bBearer\s+[A-Za-z0-9._~+/=-]{8,}"
    r"|"
    r"\b(?:api[_-]?key|secret|token)\s*[:=]\s*['\"]?\S+",
    re.IGNORECASE,
)


def _redact(text: str | bytes | None) -> str:
    if text is None:
        return ""
    if isinstance(text, bytes):
        text = text.decode("utf-8", errors="replace")
    return _SECRET_RE.sub("[REDACTED_SECRET]", str(text))


def _clip(text: str, limit: int = 2000) -> str:
    if len(text) <= limit:
        return text
    return f"{text[:limit]}... [truncated]"


def _diagnostics(stdout: str | bytes | None, stderr: str | bytes | None) -> str:
    safe_stdout = _clip(_redact(stdout))
    safe_stderr = _clip(_redact(stderr))
    parts = []
    if safe_stderr:
        parts.append(f"stderr={safe_stderr!r}")
    if safe_stdout:
        parts.append(f"stdout={safe_stdout!r}")
    return " ".join(parts) if parts else "No stdout/stderr details."


def _same_text(left: Any, right: Any) -> bool:
    if left is None or right is None:
        return False
    return str(left).casefold() == str(right).casefold()
