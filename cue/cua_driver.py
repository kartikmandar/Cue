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

    def list_windows(self) -> dict[str, Any]:
        return self.call("list_windows")

    def get_screen_size(self) -> dict[str, Any]:
        return self.call("get_screen_size")

    def get_window_state(self) -> dict[str, Any]:
        return self.call("get_window_state")

    def get_focused_element(self) -> dict[str, Any]:
        return self.call("get_focused_element")

    def get_cursor_position(self) -> dict[str, Any]:
        return self.call("get_cursor_position")

    def get_accessibility_tree(
        self, window_id: str | None = None
    ) -> dict[str, Any]:
        payload = {"window_id": window_id} if window_id is not None else None
        return self.call("get_accessibility_tree", payload)

    def open_app(self, app_name: str) -> dict[str, Any]:
        return self.call("open_app", {"app_name": app_name})

    def open_file(self, path: str | Path) -> dict[str, Any]:
        return self.call("open_file", {"path": str(path)})

    def activate_app(self, app_name: str) -> dict[str, Any]:
        return self.call("activate_app", {"app_name": app_name})

    def click(self, x: int, y: int) -> dict[str, Any]:
        return self.call("click", {"x": x, "y": y})

    def type_text(self, text: str) -> dict[str, Any]:
        return self.call("type_text", {"text": text})

    def hotkey(self, keys: list[str]) -> dict[str, Any]:
        return self.call("hotkey", {"keys": keys})

    def press_key(self, key: str) -> dict[str, Any]:
        return self.call("press_key", {"key": key})

    def scroll(self, direction: str, amount: int) -> dict[str, Any]:
        return self.call("scroll", {"direction": direction, "amount": amount})

    def set_value(self, element_id: str, value: str) -> dict[str, Any]:
        return self.call("set_value", {"element_id": element_id, "value": value})

    def focus_element(self, element_id: str) -> dict[str, Any]:
        return self.call("focus_element", {"element_id": element_id})


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
