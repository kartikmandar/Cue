from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any

from cue.agent_models import VerificationResult, WorkflowStep
from cue.context import DesktopObservation


@dataclass(frozen=True)
class VerificationExpectation:
    app: str | None = None
    window: str | None = None
    focus: str | None = None
    text: str | None = None

    @classmethod
    def from_step(cls, step: WorkflowStep) -> "VerificationExpectation":
        action = step.action
        return cls(
            app=action.expected_app or _payload_text(action.payload, "app_name", "app"),
            window=action.expected_window or _payload_text(action.payload, "window_title"),
            focus=action.expected_focus or _payload_text(action.payload, "focus"),
            text=_payload_text(action.payload, "text", "value"),
        )

    def has_concrete_state(self) -> bool:
        return any((self.app, self.window, self.focus, self.text))

    def summary(self) -> str:
        parts = []
        if self.app:
            parts.append(f"app={self.app}")
        if self.window:
            parts.append(f"window={self.window}")
        if self.focus:
            parts.append(f"focus={self.focus}")
        if self.text:
            parts.append(f"text={self.text}")
        return "; ".join(parts) or "no concrete expected state"


class Verifier:
    def __init__(
        self,
        observer: Callable[[], DesktopObservation | Mapping[str, Any]],
    ) -> None:
        self._observer = observer

    def verify_step(self, step: WorkflowStep) -> VerificationResult:
        expectation = VerificationExpectation.from_step(step)
        if not expectation.has_concrete_state():
            return VerificationResult(
                status="unknown",
                reason="No concrete expected state was provided for verification.",
                expected=expectation.summary(),
                actual=None,
                next_recommendation="Ask for a clearer expected app, window, focus, or text state.",
            )

        try:
            observation = self._observer()
        except Exception as exc:  # pragma: no cover - adapter boundary
            return VerificationResult(
                status="unknown",
                reason=f"Re-observation failed: {exc}",
                expected=expectation.summary(),
                actual=None,
                next_recommendation="Re-observe before continuing.",
            )

        actual = _actual_state(observation)
        mismatches = _mismatches(expectation, actual)
        if mismatches:
            return VerificationResult(
                status="failed",
                reason="Expected state mismatch: " + ", ".join(mismatches) + ".",
                expected=expectation.summary(),
                actual=_actual_summary(actual),
                next_recommendation="Pause, narrate the mismatch, and re-observe before retrying.",
            )

        return VerificationResult(
            status="passed",
            reason="Observed app, window, focus, and text matched the expected state.",
            expected=expectation.summary(),
            actual=_actual_summary(actual),
            next_recommendation="Continue to the next approved step.",
        )


def verify_step(
    step: WorkflowStep,
    observer: Callable[[], DesktopObservation | Mapping[str, Any]],
) -> VerificationResult:
    return Verifier(observer).verify_step(step)


def _payload_text(payload: Mapping[str, Any], *keys: str) -> str | None:
    for key in keys:
        value = payload.get(key)
        if value is None:
            continue
        text = str(value).strip()
        if text:
            return text
    return None


def _actual_state(
    observation: DesktopObservation | Mapping[str, Any],
) -> dict[str, str | None]:
    if isinstance(observation, DesktopObservation):
        focus = observation.focused_element
        focus_parts = [focus.role, focus.title, focus.value]
        text = _observation_text(observation)
        return {
            "app": observation.active_app,
            "window": observation.active_window,
            "focus": " ".join(part for part in focus_parts if part) or None,
            "text": text,
        }

    focus_value = observation.get("focused_element") or observation.get("focus")
    focus = _mapping_text(focus_value)
    return {
        "app": _first_text(observation.get("active_app"), observation.get("app")),
        "window": _first_text(
            observation.get("active_window"),
            observation.get("window"),
            observation.get("window_title"),
        ),
        "focus": focus,
        "text": " ".join(
            part
            for part in (
                _mapping_text(focus_value),
                _mapping_text(observation.get("accessibility_tree")),
                _mapping_text(observation.get("windows")),
            )
            if part
        )
        or None,
    }


def _mismatches(
    expectation: VerificationExpectation,
    actual: Mapping[str, str | None],
) -> list[str]:
    checks = [
        ("app", expectation.app, actual.get("app")),
        ("window", expectation.window, actual.get("window")),
        ("focus", expectation.focus, actual.get("focus")),
        ("text", expectation.text, actual.get("text")),
    ]
    return [
        f"{label} expected {expected!r} but saw {actual_value!r}"
        for label, expected, actual_value in checks
        if expected and not _contains(actual_value, expected)
    ]


def _actual_summary(actual: Mapping[str, str | None]) -> str:
    parts = []
    for key in ("app", "window", "focus", "text"):
        value = actual.get(key)
        if value:
            parts.append(f"{key}={value}")
    return "; ".join(parts) or "unknown actual state"


def _observation_text(observation: DesktopObservation) -> str | None:
    parts = [
        observation.focused_element.value,
        _mapping_text(observation.accessibility_tree),
        _mapping_text(observation.windows),
    ]
    return " ".join(part for part in parts if part) or None


def _mapping_text(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, str):
        return value
    if isinstance(value, Mapping):
        parts = [
            _mapping_text(item)
            for item in value.values()
            if isinstance(item, (str, Mapping, list, tuple))
        ]
        return " ".join(part for part in parts if part) or None
    if isinstance(value, list | tuple):
        parts = [_mapping_text(item) for item in value]
        return " ".join(part for part in parts if part) or None
    return None


def _first_text(*values: Any) -> str | None:
    for value in values:
        if value is None:
            continue
        text = str(value).strip()
        if text:
            return text
    return None


def _contains(actual: str | None, expected: str) -> bool:
    if actual is None:
        return False
    return expected.casefold() in actual.casefold()
