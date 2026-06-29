from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime
from time import perf_counter
from typing import Any

from cue.agent_models import PlanReview, WorkflowPlan
from cue.chat import (
    assistant_message_for_session,
    conversation_id as make_conversation_id,
    conversational_reply,
    is_conversation_only,
    mode_for_session,
    suggested_replies,
)
from cue.cli import CuaActionExecutor, LocalCliPlanner, observe_desktop
from cue.config import Settings, load_settings
from cue.context import DesktopObservation
from cue.memory import SessionMemory
from cue.narrator import Narrator
from cue.policy import ApprovalTier
from cue.redaction import redact_for_persistence
from cue.reviewer import review_plan
from cue.session import CueSessionOrchestrator, SessionState


Observer = Callable[[], DesktopObservation | Mapping[str, Any]]
Planner = Callable[[str, DesktopObservation | Mapping[str, Any]], WorkflowPlan]
Reviewer = Callable[[WorkflowPlan], PlanReview]
Executor = Callable[[Any], Any]


class SessionNotFound(KeyError):
    def __init__(self, session_id: str) -> None:
        super().__init__(session_id)
        self.session_id = session_id

    def __str__(self) -> str:
        return f"Unknown Cue session id: {self.session_id}"


class _CachingObserver:
    def __init__(self, observer: Observer) -> None:
        self._observer = observer
        self.last: DesktopObservation | Mapping[str, Any] | None = None

    def __call__(self) -> DesktopObservation | Mapping[str, Any]:
        self.last = self._observer()
        return self.last


@dataclass
class _SessionRuntime:
    orchestrator: CueSessionOrchestrator
    observer: _CachingObserver
    audit_events: list[dict[str, Any]] = field(default_factory=list)


class CueBackend:
    """In-memory backend lifecycle service for the native app MVP."""

    def __init__(
        self,
        *,
        settings: Settings,
        observer: Observer,
        planner: Planner,
        reviewer: Reviewer | None = None,
        executor: Executor | None = None,
        verifier: Any | None = None,
        narrator: Narrator | None = None,
        memory_factory: Callable[[str], SessionMemory | None] | None = None,
    ) -> None:
        self.settings = settings
        self._observer = observer
        self._planner = planner
        self._reviewer = reviewer or review_plan
        self._executor = executor
        self._verifier = verifier
        self._narrator = narrator or Narrator()
        self._memory_factory = memory_factory
        self._sessions: dict[str, _SessionRuntime] = {}
        self._current_session_id: str | None = None

    def preview(self, request: str) -> dict[str, Any]:
        start = perf_counter()
        runtime = self._new_runtime()
        session = runtime.orchestrator.preview(request)
        self._sessions[session.session_id] = runtime
        self._current_session_id = session.session_id
        self._record_event(runtime, "preview", session)
        if session.state == SessionState.BLOCKED.value:
            self._record_event(runtime, "block", session)
        return self._response(runtime, session, started_at=start)

    def set_yolo_mode(self, enabled: bool) -> dict[str, str | bool]:
        return self.set_mode(yolo_mode=enabled)

    def set_mode(
        self,
        *,
        yolo_mode: bool | None = None,
        model_provider: str | None = None,
    ) -> dict[str, str | bool]:
        updates: dict[str, Any] = {}
        if yolo_mode is not None:
            updates["yolo_mode"] = yolo_mode
        if model_provider is not None:
            if model_provider not in {"cerebras", "openrouter"}:
                raise ValueError("model_provider must be cerebras or openrouter")
            if model_provider == "openrouter" and not self.settings.openrouter_api_key:
                raise ValueError("OPENROUTER_API_KEY is required for OpenRouter mode")
            updates["model_provider"] = model_provider
        if updates:
            self.settings = self.settings.model_copy(update=updates)
        if hasattr(self._planner, "settings"):
            self._planner.settings = self.settings
        for runtime in self._sessions.values():
            runtime.orchestrator.settings = self.settings
        return self.mode()

    def mode(self) -> dict[str, str | bool]:
        return {
            "yolo_mode": self.settings.yolo_mode,
            "model_provider": self.settings.model_provider,
            "model": _active_model(self.settings),
        }

    def chat(
        self,
        request: str,
        *,
        conversation_id: str | None = None,
    ) -> dict[str, Any]:
        chat_id = make_conversation_id(conversation_id)
        text = request.strip()
        if is_conversation_only(text):
            return {
                "conversation_id": chat_id,
                "assistant_message": conversational_reply(text),
                "mode": "conversation",
                "session": None,
                "suggested_replies": suggested_replies(text),
            }

        session = self.preview(text)
        return {
            "conversation_id": chat_id,
            "assistant_message": assistant_message_for_session(session),
            "mode": mode_for_session(session),
            "session": session,
            "suggested_replies": suggested_replies(text),
        }

    def approve(self, session_id: str, *, actor: str = "user") -> dict[str, Any]:
        start = perf_counter()
        runtime = self._runtime(session_id)
        session = runtime.orchestrator.approve(actor=actor)
        self._record_event(runtime, "confirmation", session, actor=actor)
        return self._response(runtime, session, started_at=start)

    def next(self, session_id: str) -> dict[str, Any]:
        start = perf_counter()
        runtime = self._runtime(session_id)
        session = runtime.orchestrator.execute_next_step()
        event_type = (
            "block" if session.state == SessionState.BLOCKED.value else "execution"
        )
        self._record_event(runtime, event_type, session)
        if session.last_verification is not None:
            self._record_event(runtime, "verification_result", session)
        return self._response(runtime, session, started_at=start)

    def request_review(self, session_id: str) -> dict[str, Any]:
        start = perf_counter()
        runtime = self._runtime(session_id)
        session = runtime.orchestrator.request_review()
        self._record_event(runtime, "reviewer_request", session)
        return self._response(runtime, session, started_at=start)

    def confirm_reviewer(
        self,
        session_id: str,
        *,
        approved: bool,
        actor: str = "reviewer",
        reason: str | None = None,
    ) -> dict[str, Any]:
        start = perf_counter()
        runtime = self._runtime(session_id)
        if approved:
            session = runtime.orchestrator.reviewer_approve(actor=actor)
        else:
            session = runtime.orchestrator.reviewer_deny(
                actor=actor,
                reason=reason or "Reviewer denied the workflow.",
            )
        self._record_event(runtime, "reviewer_decision", session, actor=actor)
        return self._response(runtime, session, started_at=start)

    def cancel(
        self,
        session_id: str,
        *,
        reason: str = "Workflow cancelled.",
    ) -> dict[str, Any]:
        start = perf_counter()
        runtime = self._runtime(session_id)
        session = runtime.orchestrator.cancel(reason)
        self._record_event(runtime, "cancel", session)
        return self._response(runtime, session, started_at=start)

    def get_session(self, session_id: str) -> dict[str, Any]:
        start = perf_counter()
        runtime = self._runtime(session_id)
        session = runtime.orchestrator.inspect_current_session()
        return self._response(runtime, session, started_at=start)

    def audit_events(self, session_id: str | None = None) -> list[dict[str, Any]]:
        target_id = session_id or self._current_session_id
        if target_id is None:
            return []
        runtime = self._runtime(target_id)
        return [dict(event) for event in runtime.audit_events]

    def _new_runtime(self) -> _SessionRuntime:
        observer = _CachingObserver(self._observer)
        orchestrator = CueSessionOrchestrator(
            settings=self.settings,
            observer=observer,
            planner=self._planner,
            reviewer=self._reviewer,
            executor=self._executor,
            verifier=self._verifier,
            narrator=self._narrator,
            memory=self._memory_for_new_session(),
        )
        return _SessionRuntime(orchestrator=orchestrator, observer=observer)

    def _runtime(self, session_id: str) -> _SessionRuntime:
        try:
            return self._sessions[session_id]
        except KeyError as exc:
            raise SessionNotFound(session_id) from exc

    def _memory_for_new_session(self) -> SessionMemory | None:
        if not self.settings.memory_enabled:
            return None
        if self._memory_factory:
            return self._memory_factory(self.settings.session_state_path)
        return SessionMemory(self.settings.session_state_path)

    def _record_event(
        self,
        runtime: _SessionRuntime,
        event_type: str,
        session: Any,
        *,
        actor: str | None = None,
    ) -> None:
        plan = session.plan
        verification = session.last_verification
        workflow_id = (
            plan.workflow_id if plan and plan.workflow_id else session.session_id
        )
        summary = _event_summary(event_type, session)
        if actor:
            summary = f"{actor}: {summary}"
        record = {
            "timestamp": datetime.now(UTC).isoformat(),
            "event_type": event_type,
            "session_id": session.session_id,
            "workflow_id": workflow_id,
            "state": session.state,
            "current_step_id": session.current_step_id,
            "approval_tier": _approval_tier(plan, session.state),
            "policy_reason": _policy_reason(plan, session.state),
            "verification_status": verification.status
            if verification
            else "not_started",
            "summary": redact_for_persistence(summary),
        }
        runtime.audit_events.append(record)

    def _response(
        self,
        runtime: _SessionRuntime,
        session: Any,
        *,
        started_at: float,
    ) -> dict[str, Any]:
        payload = session.model_dump(mode="json")
        plan = session.plan
        plan_payload = payload.get("plan")
        events = [dict(event) for event in runtime.audit_events]
        backend_ms = max(0, int((perf_counter() - started_at) * 1000))
        payload.update(
            {
                "workflow_plan": plan_payload,
                "state_summary": _state_summary(session, runtime.observer.last),
                "focus": _focus_payload(runtime.observer.last),
                "risk": {
                    "level": plan.risk_level if plan else "unknown",
                    "approval_tier": _approval_tier(plan, session.state),
                    "risk_reasons": list(plan.risk_reasons) if plan else [],
                },
                "policy_decision": {
                    "allowed": _policy_allowed(plan, session.state),
                    "approval_tier": _approval_tier(plan, session.state),
                    "reason": _policy_reason(plan, session.state),
                    "requires_reviewer_approval": bool(
                        plan and plan.requires_reviewer_approval
                    ),
                    "redaction_applied": bool(plan and plan.redaction_applied),
                },
                "confirmation_prompt": plan.confirmation_prompt if plan else None,
                "timing": {"backend_ms": backend_ms},
                "audit_summary": [event["summary"] for event in events],
                "audit_events": events,
            }
        )
        return payload


def create_backend(settings: Settings | None = None) -> CueBackend:
    loaded_settings = settings or load_settings()
    return CueBackend(
        settings=loaded_settings,
        observer=observe_desktop,
        planner=LocalCliPlanner(settings=loaded_settings),
        executor=CuaActionExecutor(),
        narrator=Narrator(),
    )


def _active_model(settings: Settings) -> str:
    if settings.model_provider == "openrouter":
        return settings.openrouter_model
    return settings.cerebras_model


def _event_summary(event_type: str, session: Any) -> str:
    plan = session.plan
    narration = session.narration.summary if session.narration else ""
    if event_type == "verification_result" and session.last_verification:
        return session.last_verification.reason
    if plan and plan.audit_event_summary:
        return plan.audit_event_summary
    return narration or f"Cue session {session.state}."


def _state_summary(
    session: Any,
    observation: DesktopObservation | Mapping[str, Any] | None,
) -> dict[str, Any]:
    focus = _focus_payload(observation)
    return {
        "state": session.state,
        "current_step_id": session.current_step_id,
        "verified_steps": list(session.verified_steps),
        "active_app": focus.get("active_app"),
        "active_window": focus.get("active_window"),
        "last_observation_summary": _observation_summary(focus),
    }


def _focus_payload(
    observation: DesktopObservation | Mapping[str, Any] | None,
) -> dict[str, Any]:
    if observation is None:
        return {
            "active_app": None,
            "active_window": None,
            "focused_element": {"status": "unknown", "reason": "not observed"},
            "cursor_position": {"status": "unknown", "reason": "not observed"},
            "sources": [],
        }
    if isinstance(observation, DesktopObservation):
        return {
            "active_app": observation.active_app,
            "active_window": observation.active_window,
            "focused_element": observation.focused_element.to_dict(),
            "cursor_position": observation.cursor_position.to_dict(),
            "sources": list(observation.sources),
        }
    focus = observation.get("focused_element") or observation.get("focus")
    cursor = observation.get("cursor_position") or observation.get("cursor")
    return {
        "active_app": observation.get("active_app") or observation.get("app"),
        "active_window": observation.get("active_window")
        or observation.get("window")
        or observation.get("window_title"),
        "focused_element": focus if isinstance(focus, dict) else {"value": focus},
        "cursor_position": cursor if isinstance(cursor, dict) else {"value": cursor},
        "sources": list(observation.get("sources", [])),
    }


def _observation_summary(focus: Mapping[str, Any]) -> str:
    app = focus.get("active_app") or "unknown app"
    window = focus.get("active_window") or "unknown window"
    element = focus.get("focused_element") or {}
    if isinstance(element, Mapping):
        label = element.get("title") or element.get("value") or element.get("role")
    else:
        label = str(element)
    return redact_for_persistence(
        f"Active app {app}; window {window}; focus {label or 'unknown'}."
    )


def _approval_tier(plan: WorkflowPlan | None, state: str) -> str:
    if state == SessionState.BLOCKED.value:
        return ApprovalTier.BLOCKED.value
    if plan is None:
        return ApprovalTier.INFORM_ONLY.value
    return plan.approval_tier.value


def _policy_allowed(plan: WorkflowPlan | None, state: str) -> bool:
    if state == SessionState.BLOCKED.value:
        return False
    if plan is None:
        return True
    return plan.allowed_by_policy


def _policy_reason(plan: WorkflowPlan | None, state: str) -> str:
    if state == SessionState.BLOCKED.value:
        return "Blocked by Cue safety policy."
    if plan is None:
        return "No workflow policy decision is available."
    return plan.policy_reason
