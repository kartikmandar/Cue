from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import json
from pathlib import Path
import re
from typing import Any

from cue.policy import ApprovalTier
from cue.redaction import redact_text


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


_RAW_REFERENCE_RE = re.compile(
    r"\b(?:raw_)?screenshot\s*[:=]\s*\S+|\bfull_document\s*[:=]\s*\S+",
    re.IGNORECASE,
)
_PROMPT_LABEL_RE = re.compile(r"\bprompt\s*:", re.IGNORECASE)


def _tier_value(approval_tier: ApprovalTier | str) -> str:
    if isinstance(approval_tier, Enum):
        return str(approval_tier.value)
    return str(approval_tier)


def _safe_summary(summary: str) -> str:
    without_raw_refs = _RAW_REFERENCE_RE.sub("[REDACTED_RAW_CAPTURE]", summary)
    without_prompt_label = _PROMPT_LABEL_RE.sub("request summary:", without_raw_refs)
    redacted = redact_text(without_prompt_label)
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
