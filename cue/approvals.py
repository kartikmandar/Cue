from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Callable
from uuid import uuid4

from cue.policy import ApprovalTier, PolicyDecision


class ApprovalStatus(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    DENIED = "denied"
    EXPIRED = "expired"
    CANCELED = "canceled"


@dataclass(frozen=True)
class ApprovalRequest:
    request_id: str
    session_id: str
    workflow_id: str
    app: str
    action_type: str
    approval_tier: ApprovalTier
    policy_reason: str
    risk_reasons: list[str]
    requires_reviewer_approval: bool
    redaction_required: bool
    summary: str
    requested_at: datetime
    expires_at: datetime
    status: ApprovalStatus = ApprovalStatus.PENDING
    actor: str | None = None
    decision_reason: str = ""
    resolved_at: datetime | None = None


def approval_required(approval_tier: ApprovalTier | str) -> bool:
    tier = ApprovalTier(approval_tier)
    return tier in {
        ApprovalTier.CONFIRM_EACH_ACTION,
        ApprovalTier.CONFIRM_SENSITIVE,
        ApprovalTier.GUARDIAN_REQUIRED,
    }


class ApprovalRequestStore:
    def __init__(self, now: Callable[[], datetime] | None = None) -> None:
        self._now = now or (lambda: datetime.now(timezone.utc))
        self._requests: dict[str, ApprovalRequest] = {}

    def request(
        self,
        *,
        session_id: str,
        workflow_id: str,
        app: str,
        action_type: str,
        policy_decision: PolicyDecision,
        ttl_seconds: int = 900,
    ) -> ApprovalRequest:
        if not policy_decision.allowed or policy_decision.approval_tier == (
            ApprovalTier.BLOCKED
        ):
            raise ValueError("Cannot create approval for a blocked policy decision")
        if not approval_required(policy_decision.approval_tier):
            raise ValueError("No approval is required for inform-only decisions")

        requested_at = self._now()
        approval = ApprovalRequest(
            request_id=uuid4().hex,
            session_id=session_id,
            workflow_id=workflow_id,
            app=app,
            action_type=action_type,
            approval_tier=policy_decision.approval_tier,
            policy_reason=policy_decision.reason,
            risk_reasons=list(policy_decision.risk_reasons),
            requires_reviewer_approval=policy_decision.requires_reviewer_approval,
            redaction_required=policy_decision.redaction_required,
            summary=policy_decision.audit_event_summary,
            requested_at=requested_at,
            expires_at=requested_at + timedelta(seconds=ttl_seconds),
        )
        self._requests[approval.request_id] = approval
        return approval

    def get(self, request_id: str) -> ApprovalRequest:
        try:
            return self._requests[request_id]
        except KeyError as exc:
            raise KeyError(f"Unknown approval request: {request_id}") from exc

    def approve(
        self,
        request_id: str,
        actor: str,
        decision_reason: str = "",
    ) -> ApprovalRequest:
        return self._resolve(
            request_id,
            ApprovalStatus.APPROVED,
            actor=actor,
            decision_reason=decision_reason,
        )

    def deny(
        self,
        request_id: str,
        actor: str,
        decision_reason: str = "",
    ) -> ApprovalRequest:
        return self._resolve(
            request_id,
            ApprovalStatus.DENIED,
            actor=actor,
            decision_reason=decision_reason,
        )

    def expire(self, request_id: str) -> ApprovalRequest:
        return self._resolve(request_id, ApprovalStatus.EXPIRED, actor=None)

    def cancel(self, request_id: str, decision_reason: str = "") -> ApprovalRequest:
        return self._resolve(
            request_id,
            ApprovalStatus.CANCELED,
            actor=None,
            decision_reason=decision_reason,
        )

    def _resolve(
        self,
        request_id: str,
        status: ApprovalStatus,
        *,
        actor: str | None,
        decision_reason: str = "",
    ) -> ApprovalRequest:
        current = self.get(request_id)
        if current.status != ApprovalStatus.PENDING:
            raise ValueError(f"Approval request {request_id} is not pending")

        now = self._now()
        if status in {ApprovalStatus.APPROVED, ApprovalStatus.DENIED}:
            if now >= current.expires_at:
                expired = replace(
                    current,
                    status=ApprovalStatus.EXPIRED,
                    resolved_at=now,
                )
                self._requests[request_id] = expired
                raise ValueError(f"Approval request {request_id} is not pending")

        resolved = replace(
            current,
            status=status,
            actor=actor,
            decision_reason=decision_reason,
            resolved_at=now,
        )
        self._requests[request_id] = resolved
        return resolved
