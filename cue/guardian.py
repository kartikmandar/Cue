from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Callable
from uuid import uuid4

from cue.policy import ApprovalTier


class GuardianApprovalStatus(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    DENIED = "denied"
    EXPIRED = "expired"
    CANCELED = "canceled"


@dataclass(frozen=True)
class GuardianApproval:
    request_id: str
    session_id: str
    workflow_id: str
    approval_tier: ApprovalTier
    summary: str
    reason: str
    risk_reasons: list[str]
    requested_at: datetime
    expires_at: datetime
    status: GuardianApprovalStatus = GuardianApprovalStatus.PENDING
    reviewer_id: str | None = None
    decision_reason: str = ""
    resolved_at: datetime | None = None


class GuardianApprovalStore:
    def __init__(self, now: Callable[[], datetime] | None = None) -> None:
        self._now = now or (lambda: datetime.now(timezone.utc))
        self._requests: dict[str, GuardianApproval] = {}

    def request(
        self,
        *,
        session_id: str,
        workflow_id: str,
        approval_tier: ApprovalTier,
        summary: str,
        reason: str,
        risk_reasons: list[str],
        ttl_seconds: int = 900,
    ) -> GuardianApproval:
        requested_at = self._now()
        approval = GuardianApproval(
            request_id=uuid4().hex,
            session_id=session_id,
            workflow_id=workflow_id,
            approval_tier=approval_tier,
            summary=summary,
            reason=reason,
            risk_reasons=list(risk_reasons),
            requested_at=requested_at,
            expires_at=requested_at + timedelta(seconds=ttl_seconds),
        )
        self._requests[approval.request_id] = approval
        return approval

    def get(self, request_id: str) -> GuardianApproval:
        try:
            return self._requests[request_id]
        except KeyError as exc:
            raise KeyError(f"Unknown guardian approval request: {request_id}") from exc

    def approve(
        self,
        request_id: str,
        reviewer_id: str,
        decision_reason: str = "",
    ) -> GuardianApproval:
        return self._resolve(
            request_id,
            GuardianApprovalStatus.APPROVED,
            reviewer_id=reviewer_id,
            decision_reason=decision_reason,
        )

    def deny(
        self,
        request_id: str,
        reviewer_id: str,
        decision_reason: str = "",
    ) -> GuardianApproval:
        return self._resolve(
            request_id,
            GuardianApprovalStatus.DENIED,
            reviewer_id=reviewer_id,
            decision_reason=decision_reason,
        )

    def expire(self, request_id: str) -> GuardianApproval:
        return self._resolve(request_id, GuardianApprovalStatus.EXPIRED)

    def cancel(self, request_id: str, decision_reason: str = "") -> GuardianApproval:
        return self._resolve(
            request_id,
            GuardianApprovalStatus.CANCELED,
            decision_reason=decision_reason,
        )

    def _resolve(
        self,
        request_id: str,
        status: GuardianApprovalStatus,
        *,
        reviewer_id: str | None = None,
        decision_reason: str = "",
    ) -> GuardianApproval:
        current = self.get(request_id)
        if current.status != GuardianApprovalStatus.PENDING:
            raise ValueError(f"Guardian approval request {request_id} is not pending")

        now = self._now()
        if status in {GuardianApprovalStatus.APPROVED, GuardianApprovalStatus.DENIED}:
            if now >= current.expires_at:
                expired = replace(
                    current,
                    status=GuardianApprovalStatus.EXPIRED,
                    resolved_at=now,
                )
                self._requests[request_id] = expired
                raise ValueError(
                    f"Guardian approval request {request_id} is not pending"
                )

        resolved = replace(
            current,
            status=status,
            reviewer_id=reviewer_id,
            decision_reason=decision_reason,
            resolved_at=now,
        )
        self._requests[request_id] = resolved
        return resolved
