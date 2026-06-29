from __future__ import annotations

import argparse
from collections.abc import Callable, Sequence
from typing import Any

from cue.actions import ActionType, CueAction, WorkflowCategory
from cue.agent_models import (
    IntentResult,
    VerificationResult,
    WorkflowPlan,
    WorkflowSession,
    WorkflowStep,
)
from cue.config import Settings, load_settings
from cue.context import DesktopObservation
from cue.cua_driver import CuaDriver
from cue.focus import (
    CursorPosition,
    FocusedElement,
    normalize_active_window,
    normalize_cursor_position,
    normalize_focused_element,
)
from cue.input_agent import normalize_input
from cue.intent_agent import classify_intent
from cue.narrator import Narrator
from cue.policy import ApprovalTier
from cue.session import CueSessionOrchestrator
from cue.speech import speak
from cue.workflows import create_document_workflow


Observer = Callable[[], DesktopObservation]
Planner = Callable[[str, DesktopObservation], WorkflowPlan]
Executor = Callable[[CueAction], Any]
Speaker = Callable[..., None]


def main(
    argv: Sequence[str] | None = None,
    *,
    settings: Settings | None = None,
    observer: Observer | None = None,
    planner: Planner | None = None,
    executor: Executor | None = None,
    speaker: Speaker = speak,
) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    settings = settings or load_settings()

    if args.cancel:
        print("Cancel requested. No persistent CLI workflow is active.")
        return 0

    if args.input_mode == "voice":
        return _voice_placeholder(settings)

    request = " ".join(args.request).strip()
    if not request:
        print("Request text is required for text input mode.")
        return 2

    caching_observer = _CachingObserver(observer or observe_desktop)
    session = CueSessionOrchestrator(
        settings=settings,
        observer=caching_observer,
        planner=planner or LocalCliPlanner(settings=settings),
        executor=executor or CuaActionExecutor(),
        narrator=Narrator(),
    )

    messages: list[str] = []
    workflow = session.preview(request)

    if args.approve:
        workflow = session.approve(actor="cli")

    if args.next:
        if args.read_only:
            messages.append("Read-only mode prevented execution of the next step.")
        elif not args.approve:
            messages.append(
                "Next step was not executed because approval is required."
            )
        else:
            try:
                workflow = session.execute_next_step()
            except Exception as exc:  # pragma: no cover - defensive CLI boundary
                messages.append(f"Execution failed: {exc}")

    _print_session(
        workflow,
        observation=caching_observer.last,
        messages=messages,
        speaker=speaker,
        speech_enabled=settings.speak and not args.no_speak,
    )
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="cue",
        description="Cue developer CLI for safe desktop workflow previews.",
    )
    parser.add_argument("request", nargs="*", help="Request text for Cue.")
    parser.add_argument(
        "--input-mode",
        choices=("text", "voice"),
        default="text",
        help="Input source. Voice is a placeholder unless explicitly enabled.",
    )
    parser.add_argument(
        "--approve",
        action="store_true",
        help="Approve the previewed workflow for this invocation.",
    )
    parser.add_argument(
        "--next",
        action="store_true",
        help="Attempt the next approved workflow step.",
    )
    parser.add_argument(
        "--cancel",
        action="store_true",
        help="Cancel a pending workflow in this stateless CLI invocation.",
    )
    parser.add_argument(
        "--no-speak",
        action="store_true",
        help="Print narration without invoking macOS speech output.",
    )
    parser.add_argument(
        "--read-only",
        action="store_true",
        help="Preview only; do not execute desktop actions.",
    )
    return parser


def observe_desktop(driver: CuaDriver | None = None) -> DesktopObservation:
    cua = driver or CuaDriver()
    apps, apps_source = _safe_driver_call(cua.list_apps, "cua:list_apps")
    windows, windows_source = _safe_driver_call(cua.list_windows, "cua:list_windows")
    app_items = _coerce_items(apps, "apps")
    window_items = _coerce_items(windows, "windows")
    active_app = _active_app_name(app_items)
    active_window_record = _active_window(window_items, active_app)
    if active_window_record:
        pid = int(active_window_record["pid"])
        window_id = int(active_window_record["window_id"])
        window_state, window_source = _safe_driver_call(
            lambda: cua.get_window_state(pid=pid, window_id=window_id),
            "cua:get_window_state",
        )
    else:
        window_state, window_source = _safe_driver_call(
            cua.get_window_state,
            "cua:get_window_state",
        )
    focus_raw, focus_source = _safe_driver_call(
        cua.get_focused_element,
        "cua:get_focused_element",
    )
    cursor_raw, cursor_source = _safe_driver_call(
        cua.get_cursor_position,
        "cua:get_cursor_position",
    )
    screen_size, screen_source = _safe_driver_call(
        cua.get_screen_size,
        "cua:get_screen_size",
    )
    accessibility_tree, tree_source = _safe_driver_call(
        cua.get_accessibility_tree,
        "cua:get_accessibility_tree",
    )

    state_app, state_window = normalize_active_window(window_state)
    resolved_app = active_app or _window_app(active_window_record) or state_app
    resolved_window = _window_title(active_window_record) or state_window
    focus = _normalize_focus(focus_raw, focus_source)
    cursor = _normalize_cursor(cursor_raw, cursor_source)
    return DesktopObservation(
        active_app=resolved_app,
        active_window=resolved_window,
        focused_element=focus,
        cursor_position=cursor,
        apps=app_items,
        windows=window_items,
        accessibility_tree=accessibility_tree if isinstance(accessibility_tree, dict) else None,
        screen_size=screen_size if isinstance(screen_size, dict) else None,
        screenshot_ref=None,
        sources=[
            apps_source,
            windows_source,
            window_source,
            focus.source,
            cursor.source,
            screen_source,
            tree_source,
        ],
    )


class LocalCliPlanner:
    def __init__(self, *, settings: Settings) -> None:
        self.settings = settings

    def __call__(
        self,
        request: str,
        observation: DesktopObservation,
    ) -> WorkflowPlan:
        normalized = normalize_input(request, source="cli")
        intent = classify_intent(normalized)
        if not intent.workflow_required:
            return _answer_plan(intent, observation)
        if intent.workflow_category == WorkflowCategory.SENSITIVE:
            return _blocked_sensitive_plan(intent)
        if _is_task_16_textedit_document_request(intent):
            return create_document_workflow(
                title=_textedit_title(intent.normalized_input.text),
                settings=self.settings,
                apply_heading="heading" in intent.normalized_input.text.casefold(),
                focus_verified=observation.focused_element.status == "known",
            )

        action = _planned_action(intent, observation, self.settings)
        steps = [
            WorkflowStep(
                step_id="step-1",
                title=_step_title(action),
                action=action,
                expected_outcome=_expected_outcome(action),
                verification_criteria=_verification_criteria(action),
            )
        ]
        if action.changes_state:
            steps.append(_verify_step(action))

        return WorkflowPlan(
            intent=intent,
            narration="Cue prepared a local-safe workflow preview.",
            workflow_required=True,
            workflow_category=intent.workflow_category,
            steps=steps,
            risk_level=intent.risk_level,
            approval_tier=ApprovalTier.CONFIRM_EACH_ACTION,
            confirmation_prompt="Approve this workflow before any desktop action?",
            expected_outcome=_expected_outcome(action),
            risk_reasons=list(intent.risk_reasons),
            requires_reviewer_approval=False,
            redaction_applied=False,
            allowed_by_policy=True,
            policy_reason="Local CLI preview uses policy checks before execution.",
            audit_event_summary="Local CLI workflow preview.",
            workflow_id="cli-workflow",
        )


class CuaActionExecutor:
    def __init__(self, driver: CuaDriver | None = None) -> None:
        self.driver = driver or CuaDriver()

    def __call__(self, action: CueAction) -> Any:
        action_type = action.action_type
        payload = action.payload
        if action_type in {
            ActionType.NONE,
            ActionType.VERIFY,
            ActionType.ASK_CONFIRMATION,
            ActionType.REQUEST_REVIEWER_APPROVAL,
            ActionType.CANCEL_WORKFLOW,
            ActionType.WAIT_FOR_WINDOW,
        }:
            return {"ok": True, "action_type": action_type.value, "executed": False}
        if action_type == ActionType.OPEN_APP:
            return self.driver.open_app(_payload_text(payload, "app_name", "app"))
        if action_type == ActionType.OPEN_FILE:
            return self.driver.open_file(_payload_text(payload, "path"))
        if action_type == ActionType.ACTIVATE_APP:
            return self.driver.activate_app(_payload_text(payload, "app_name", "app"))
        if action_type == ActionType.CLICK:
            return self.driver.click(int(payload["x"]), int(payload["y"]))
        if action_type == ActionType.TYPE_TEXT:
            return self.driver.type_text(_payload_text(payload, "text", "value"))
        if action_type == ActionType.HOTKEY:
            return self.driver.hotkey([str(key) for key in payload.get("keys", [])])
        if action_type == ActionType.PRESS_KEY:
            return self.driver.press_key(_payload_text(payload, "key"))
        if action_type == ActionType.SCROLL:
            amount = int(payload.get("amount", 1))
            return self.driver.scroll(_payload_text(payload, "direction"), amount)
        if action_type == ActionType.SET_VALUE:
            return self.driver.set_value(
                _payload_text(payload, "element_id"),
                _payload_text(payload, "value", "text"),
            )
        if action_type == ActionType.FOCUS_ELEMENT:
            return self.driver.focus_element(_payload_text(payload, "element_id"))
        raise ValueError(f"Unsupported CLI action: {action_type.value}")


class _CachingObserver:
    def __init__(self, observer: Observer) -> None:
        self._observer = observer
        self.last: DesktopObservation | None = None

    def __call__(self) -> DesktopObservation:
        self.last = self._observer()
        return self.last


def _voice_placeholder(settings: Settings) -> int:
    if not settings.enable_voice_input:
        print(
            "Voice input is disabled. Set CUE_ENABLE_VOICE_INPUT=true only when "
            "a real dictation path is available."
        )
        return 2
    print(
        "Voice input is enabled in settings, but CLI transcription is not "
        "implemented yet. Use text input or the native app voice surface."
    )
    return 2


def _print_session(
    workflow: WorkflowSession,
    *,
    observation: DesktopObservation | None,
    messages: list[str],
    speaker: Speaker,
    speech_enabled: bool,
) -> None:
    for message in messages:
        print(message)

    print(f"State: {workflow.state}")
    _print_observation(observation)

    plan = workflow.plan
    print(f"Policy tier: {_approval_tier(plan)}")
    _print_plan(plan)
    _print_verification(workflow.last_verification)

    narration = workflow.narration.speakable_text if workflow.narration else ""
    if narration:
        print("Narration:")
        speaker(narration, enabled=speech_enabled)
    else:
        print("Narration: none")


def _print_observation(observation: DesktopObservation | None) -> None:
    if observation is None:
        print("Active app: unknown")
        print("Active window: unknown")
        print("Focus: unknown")
        return
    print(f"Active app: {observation.active_app or 'unknown'}")
    print(f"Active window: {observation.active_window or 'unknown'}")
    print(f"Focus: {_focus_summary(observation.focused_element)}")
    print(f"Cursor: {_cursor_summary(observation.cursor_position)}")


def _print_plan(plan: WorkflowPlan | None) -> None:
    if plan is None:
        print("Workflow plan: unavailable")
        return
    if not plan.steps:
        print("Workflow plan: No desktop action is needed.")
        return
    print("Workflow plan:")
    for index, step in enumerate(plan.steps, start=1):
        print(
            f"  {index}. {step.title} "
            f"({step.action.action_type.value}) - {step.expected_outcome}"
        )


def _print_verification(result: VerificationResult | None) -> None:
    if result is None:
        print("Verification: not_run")
        return
    print(f"Verification: {result.status} - {result.reason}")


def _approval_tier(plan: WorkflowPlan | None) -> str:
    if plan is None:
        return "unknown"
    return plan.approval_tier.value


def _answer_plan(
    intent: IntentResult,
    observation: DesktopObservation,
) -> WorkflowPlan:
    app = observation.active_app or "unknown app"
    window = observation.active_window or "unknown window"
    return WorkflowPlan(
        intent=intent,
        narration=f"Current desktop is {app}, window {window}.",
        workflow_required=False,
        workflow_category=WorkflowCategory.ANSWER,
        steps=[],
        risk_level="none",
        approval_tier=ApprovalTier.INFORM_ONLY,
        confirmation_prompt="No approval is needed for a read-only answer.",
        expected_outcome="Current app, window, and focus are narrated.",
        risk_reasons=[],
        requires_reviewer_approval=False,
        redaction_applied=False,
        allowed_by_policy=True,
        policy_reason="Read-only status request.",
        audit_event_summary="Local CLI read-only preview.",
        workflow_id="cli-readonly",
    )


def _blocked_sensitive_plan(intent: IntentResult) -> WorkflowPlan:
    return WorkflowPlan(
        intent=intent,
        narration="Cue cannot help with credentials or sensitive authentication.",
        workflow_required=True,
        workflow_category=WorkflowCategory.SENSITIVE,
        steps=[],
        risk_level="blocked",
        approval_tier=ApprovalTier.BLOCKED,
        confirmation_prompt="This request is blocked.",
        expected_outcome="No sensitive action is taken.",
        risk_reasons=list(intent.risk_reasons),
        requires_reviewer_approval=False,
        redaction_applied=True,
        allowed_by_policy=False,
        policy_reason="Sensitive authentication requests are blocked.",
        audit_event_summary="Blocked sensitive CLI request.",
        workflow_id="cli-blocked",
    )


def _planned_action(
    intent: IntentResult,
    observation: DesktopObservation,
    settings: Settings,
) -> CueAction:
    text = intent.normalized_input.text
    app = _requested_app(text, settings) or observation.active_app or "Unknown"

    if intent.workflow_category in {
        WorkflowCategory.APP_LAUNCH,
        WorkflowCategory.TERMINAL,
        WorkflowCategory.CODING,
    }:
        return CueAction(
            action_type=ActionType.OPEN_APP,
            payload={"app_name": app},
            reason=f"Open or focus {app} after approval.",
            expected_app=app,
            changes_state=True,
        )

    if intent.workflow_category == WorkflowCategory.DOCUMENT:
        return CueAction(
            action_type=ActionType.TYPE_TEXT,
            payload={"text": _document_text(text)},
            reason="Type approved text into the focused document after approval.",
            expected_app=app,
            expected_window=observation.active_window,
            expected_focus=_focus_summary(observation.focused_element),
            changes_state=True,
        )

    return CueAction(
        action_type=ActionType.NONE,
        payload={},
        reason="No supported desktop action is available from the CLI preview.",
        expected_app=observation.active_app,
        expected_window=observation.active_window,
        changes_state=False,
    )


def _verify_step(action: CueAction) -> WorkflowStep:
    return WorkflowStep(
        step_id="step-2",
        title="Verify result",
        action=CueAction(
            action_type=ActionType.VERIFY,
            payload={},
            reason="Verify the visible desktop state after the approved action.",
            expected_app=action.expected_app,
            expected_window=action.expected_window,
            expected_focus=action.expected_focus,
            changes_state=False,
        ),
        expected_outcome=_expected_outcome(action),
        verification_criteria=_verification_criteria(action),
    )


def _step_title(action: CueAction) -> str:
    if action.action_type == ActionType.OPEN_APP:
        return f"Open {action.expected_app or 'app'}"
    if action.action_type == ActionType.TYPE_TEXT:
        return "Type approved text"
    return "Preview desktop action"


def _expected_outcome(action: CueAction) -> str:
    if action.expected_app:
        return f"{action.expected_app} is active or verified."
    return "The requested desktop state is verified."


def _verification_criteria(action: CueAction) -> str:
    if action.expected_app:
        return f"Active app contains {action.expected_app}."
    return "Visible state matches the workflow expectation."


def _requested_app(text: str, settings: Settings) -> str | None:
    normalized = text.casefold()
    for app in settings.allowed_apps:
        if app.casefold() in normalized:
            return app
    if "terminal" in normalized:
        return "Terminal"
    if "textedit" in normalized or "text edit" in normalized:
        return "TextEdit"
    if "finder" in normalized:
        return "Finder"
    if "safari" in normalized:
        return "Safari"
    if "chrome" in normalized:
        return "Google Chrome"
    return None


def _is_task_16_textedit_document_request(intent: IntentResult) -> bool:
    text = intent.normalized_input.text.casefold()
    return (
        intent.workflow_category == WorkflowCategory.DOCUMENT
        and "textedit" in text
        and ("title" in text or "cursor below" in text or "project name" in text)
    )


def _textedit_title(text: str) -> str:
    if "cue" in text.casefold():
        return "Cue"
    return _document_text(text)


def _document_text(text: str) -> str:
    lowered = text.casefold()
    for marker in ("type ", "write "):
        index = lowered.find(marker)
        if index >= 0:
            value = text[index + len(marker) :]
            return value.strip() or "Cue"
    return "Cue"


def _active_app_name(apps: list[dict[str, Any]]) -> str | None:
    for app in apps:
        if app.get("active"):
            return _first_text(app.get("name"), app.get("app_name"), app.get("title"))
    return None


def _active_window(
    windows: list[dict[str, Any]],
    active_app: str | None,
) -> dict[str, Any] | None:
    candidates = [
        window
        for window in windows
        if window.get("pid") is not None
        and window.get("window_id") is not None
        and (not active_app or _same_text(_window_app(window), active_app))
    ]
    if not candidates:
        candidates = [
            window
            for window in windows
            if window.get("pid") is not None
            and window.get("window_id") is not None
            and window.get("is_on_screen")
        ]
    if not candidates:
        return None
    return max(candidates, key=lambda window: int(window.get("z_index") or 0))


def _window_app(window: dict[str, Any] | None) -> str | None:
    if not isinstance(window, dict):
        return None
    return _first_text(window.get("app_name"), window.get("app"), window.get("owner"))


def _window_title(window: dict[str, Any] | None) -> str | None:
    if not isinstance(window, dict):
        return None
    return _first_text(window.get("title"), window.get("window_title"), window.get("name"))


def _same_text(left: str | None, right: str | None) -> bool:
    if left is None or right is None:
        return False
    return left.casefold() == right.casefold()


def _first_text(*values: Any) -> str | None:
    for value in values:
        if value is None:
            continue
        text = str(value).strip()
        if text:
            return text
    return None


def _focus_summary(focus: FocusedElement) -> str:
    if focus.status != "known":
        return focus.reason or "unknown"
    parts = [focus.role, focus.title]
    return " ".join(part for part in parts if part) or "known focus"


def _cursor_summary(cursor: CursorPosition) -> str:
    if cursor.status != "known":
        return cursor.reason or "unknown"
    return f"x={cursor.x} y={cursor.y}"


def _safe_driver_call(
    call: Callable[[], dict[str, Any]],
    source: str,
) -> tuple[dict[str, Any] | None, str]:
    try:
        return call(), source
    except Exception as exc:  # pragma: no cover - adapter boundary
        return None, f"{source} unavailable: {exc}"


def _normalize_focus(
    raw: dict[str, Any] | None,
    source: str,
) -> FocusedElement:
    try:
        return normalize_focused_element(raw)
    except Exception:
        return FocusedElement.unknown(source)


def _normalize_cursor(
    raw: dict[str, Any] | None,
    source: str,
) -> CursorPosition:
    try:
        return normalize_cursor_position(raw)
    except Exception:
        return CursorPosition.unknown(source)


def _coerce_items(value: dict[str, Any] | None, key: str) -> list[dict[str, Any]]:
    if not isinstance(value, dict):
        return []
    raw_items = value.get(key) or value.get("items") or value.get("data") or []
    if not isinstance(raw_items, list):
        return []
    items: list[dict[str, Any]] = []
    for item in raw_items:
        if isinstance(item, dict):
            items.append(item)
        elif item is not None:
            items.append({"name": str(item)})
    return items


def _payload_text(payload: dict[str, Any], *keys: str) -> str:
    for key in keys:
        value = payload.get(key)
        if value is None:
            continue
        text = str(value).strip()
        if text:
            return text
    raise ValueError(f"Missing required action payload value: {', '.join(keys)}")


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
