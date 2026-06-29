"""App and file launch helpers with Cua focus verification."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import subprocess
import time

from cue.cua_driver import CuaDriver, CuaDriverError
from cue.focus import normalize_active_window


@dataclass(frozen=True)
class LaunchResult:
    ok: bool
    app_name: str | None
    window_title: str | None
    reason: str


def open_app(
    app_name: str,
    *,
    driver: CuaDriver | None = None,
    timeout_seconds: float = 10,
) -> LaunchResult:
    opened = _run_open(["open", "-a", app_name], app_name=app_name)
    if not opened.ok:
        return opened
    return wait_for_window(
        app_name=app_name,
        timeout_seconds=timeout_seconds,
        driver=driver,
    )


def open_file(
    path: str | Path,
    *,
    driver: CuaDriver | None = None,
    timeout_seconds: float = 10,
) -> LaunchResult:
    file_path = Path(path)
    opened = _run_open(["open", str(file_path)], app_name=None)
    if not opened.ok:
        return opened
    return wait_for_window(
        title_hint=file_path.name,
        timeout_seconds=timeout_seconds,
        driver=driver,
    )


def activate_app(
    app_name: str,
    *,
    driver: CuaDriver | None = None,
    timeout_seconds: float = 10,
) -> LaunchResult:
    cua = driver or CuaDriver()
    try:
        response = cua.activate_app(app_name)
    except CuaDriverError as exc:
        return LaunchResult(
            ok=False,
            app_name=app_name,
            window_title=None,
            reason=f"Cua activate_app failed: {exc}",
        )

    if response.get("ok") is False:
        return LaunchResult(
            ok=False,
            app_name=app_name,
            window_title=None,
            reason=str(response.get("reason") or "Cua activate_app returned ok=false."),
        )

    return wait_for_window(
        app_name=app_name,
        timeout_seconds=timeout_seconds,
        driver=cua,
    )


def wait_for_window(
    title_hint: str | None = None,
    app_name: str | None = None,
    timeout_seconds: float = 10,
    poll_interval: float = 0.25,
    *,
    driver: CuaDriver | None = None,
) -> LaunchResult:
    cua = driver or CuaDriver()
    deadline = time.monotonic() + timeout_seconds

    while True:
        try:
            active_app, window_title = normalize_active_window(cua.get_window_state())
        except CuaDriverError as exc:
            return LaunchResult(
                ok=False,
                app_name=app_name,
                window_title=None,
                reason=f"Cua window polling failed: {exc}",
            )

        if _matches(active_app, window_title, app_name, title_hint):
            resolved_app = active_app or app_name
            return LaunchResult(
                ok=True,
                app_name=resolved_app,
                window_title=window_title,
                reason=_active_reason(resolved_app, window_title),
            )

        if time.monotonic() >= deadline:
            return LaunchResult(
                ok=False,
                app_name=app_name,
                window_title=None,
                reason=_timeout_reason(app_name, title_hint),
            )

        time.sleep(max(0.0, min(poll_interval, deadline - time.monotonic())))


def _run_open(command: list[str], *, app_name: str | None) -> LaunchResult:
    try:
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            check=False,
            timeout=10,
        )
    except FileNotFoundError as exc:
        return LaunchResult(
            ok=False,
            app_name=app_name,
            window_title=None,
            reason=f"macOS open command unavailable: {exc}",
        )
    except subprocess.TimeoutExpired as exc:
        return LaunchResult(
            ok=False,
            app_name=app_name,
            window_title=None,
            reason=f"macOS open timed out after {exc.timeout}s.",
        )

    if result.returncode != 0:
        details = (result.stderr or result.stdout or "no stderr/stdout").strip()
        return LaunchResult(
            ok=False,
            app_name=app_name,
            window_title=None,
            reason=f"macOS open failed: {details}",
        )

    return LaunchResult(
        ok=True,
        app_name=app_name,
        window_title=None,
        reason="macOS open command completed.",
    )


def _matches(
    active_app: str | None,
    window_title: str | None,
    app_name: str | None,
    title_hint: str | None,
) -> bool:
    app_ok = app_name is None or _same_text(active_app, app_name)
    title_ok = title_hint is None or _contains_text(window_title, title_hint)
    return app_ok and title_ok and (active_app is not None or window_title is not None)


def _same_text(left: str | None, right: str | None) -> bool:
    if left is None or right is None:
        return False
    return left.casefold() == right.casefold()


def _contains_text(value: str | None, hint: str | None) -> bool:
    if value is None or hint is None:
        return False
    return hint.casefold() in value.casefold()


def _active_reason(app_name: str | None, window_title: str | None) -> str:
    app = app_name or "Requested app"
    if window_title:
        return f"{app} active with window {window_title}."
    return f"{app} active."


def _timeout_reason(app_name: str | None, title_hint: str | None) -> str:
    parts = []
    if app_name:
        parts.append(f"app {app_name!r}")
    if title_hint:
        parts.append(f"title containing {title_hint!r}")
    target = " and ".join(parts) if parts else "any active window"
    return f"Timed out waiting for {target}."

