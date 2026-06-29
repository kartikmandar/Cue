from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import json
from pathlib import Path
from typing import Any

from cue.policy import ApprovalTier
from cue.redaction import redact_for_persistence


@dataclass(frozen=True)
class AuditEvent:
    event_type: str
    session_id: str
    workflow_id: str
    app: str
    action_type: str
    approval_tier: ApprovalTier | str
    policy_reason: str
    verification_status: str
    latency_ms: int
    summary: str


TASK7_AUDIT_EVENT_TYPES = {
    "preview",
    "confirmation",
    "execution",
    "block",
    "reviewer_request",
    "reviewer_decision",
    "verification_result",
}


def _tier_value(approval_tier: ApprovalTier | str) -> str:
    if isinstance(approval_tier, Enum):
        return str(approval_tier.value)
    return str(approval_tier)


def _safe_summary(summary: str) -> str:
    redacted = redact_for_persistence(summary)
    return " ".join(redacted.split())[:500]


def append_audit_event(path: str | Path, event: AuditEvent) -> dict[str, Any]:
    record: dict[str, Any] = {
        "event_type": event.event_type,
        "session_id": event.session_id,
        "workflow_id": event.workflow_id,
        "app": event.app,
        "action_type": event.action_type,
        "approval_tier": _tier_value(event.approval_tier),
        "policy_reason": event.policy_reason,
        "verification_status": event.verification_status,
        "latency_ms": event.latency_ms,
        "summary": _safe_summary(event.summary),
    }

    log_path = Path(path)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, sort_keys=True) + "\n")
    return record


def record_audit_event(
    path: str | Path,
    *,
    event_type: str,
    session_id: str,
    workflow_id: str,
    app: str,
    action_type: str,
    approval_tier: ApprovalTier | str,
    policy_reason: str,
    verification_status: str = "not_started",
    latency_ms: int = 0,
    summary: str = "",
) -> dict[str, Any]:
    if event_type not in TASK7_AUDIT_EVENT_TYPES:
        raise ValueError(f"unsupported audit event type: {event_type}")

    return append_audit_event(
        path,
        AuditEvent(
            event_type=event_type,
            session_id=session_id,
            workflow_id=workflow_id,
            app=app,
            action_type=action_type,
            approval_tier=approval_tier,
            policy_reason=policy_reason,
            verification_status=verification_status,
            latency_ms=latency_ms,
            summary=summary,
        ),
    )
