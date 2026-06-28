from datetime import datetime, timedelta, timezone

import pytest

from cue.guardian import GuardianApprovalStore, GuardianApprovalStatus
from cue.policy import ApprovalTier


def test_guardian_request_and_approve_flow_stores_pending_state_in_memory():
    store = GuardianApprovalStore()

    approval = store.request(
        session_id="session-1",
        workflow_id="workflow-1",
        approval_tier=ApprovalTier.GUARDIAN_REQUIRED,
        summary="Delete an existing archive.",
        reason="Destructive file action.",
        risk_reasons=["guardian required for destructive action"],
    )
    resolved = store.approve(
        approval.request_id,
        reviewer_id="reviewer-1",
        decision_reason="Approved for demo.",
    )

    assert approval.status == GuardianApprovalStatus.PENDING
    assert resolved.status == GuardianApprovalStatus.APPROVED
    assert resolved.reviewer_id == "reviewer-1"
    assert store.get(approval.request_id).status == GuardianApprovalStatus.APPROVED


def test_guardian_supports_deny_expire_and_cancel():
    now = datetime(2026, 6, 29, tzinfo=timezone.utc)
    store = GuardianApprovalStore(now=lambda: now)

    denied = store.request(
        session_id="session-1",
        workflow_id="workflow-deny",
        approval_tier=ApprovalTier.GUARDIAN_REQUIRED,
        summary="High-risk workflow.",
        reason="Needs reviewer.",
        risk_reasons=["guardian required"],
    )
    expired = store.request(
        session_id="session-1",
        workflow_id="workflow-expire",
        approval_tier=ApprovalTier.GUARDIAN_REQUIRED,
        summary="High-risk workflow.",
        reason="Needs reviewer.",
        risk_reasons=["guardian required"],
        ttl_seconds=1,
    )
    canceled = store.request(
        session_id="session-1",
        workflow_id="workflow-cancel",
        approval_tier=ApprovalTier.GUARDIAN_REQUIRED,
        summary="High-risk workflow.",
        reason="Needs reviewer.",
        risk_reasons=["guardian required"],
    )

    assert store.deny(denied.request_id, "reviewer-1").status == (
        GuardianApprovalStatus.DENIED
    )
    store._now = lambda: now + timedelta(seconds=2)
    assert store.expire(expired.request_id).status == GuardianApprovalStatus.EXPIRED
    assert store.cancel(canceled.request_id).status == GuardianApprovalStatus.CANCELED


def test_guardian_rejects_resolving_non_pending_requests():
    store = GuardianApprovalStore()
    approval = store.request(
        session_id="session-1",
        workflow_id="workflow-1",
        approval_tier=ApprovalTier.GUARDIAN_REQUIRED,
        summary="High-risk workflow.",
        reason="Needs reviewer.",
        risk_reasons=["guardian required"],
    )

    store.cancel(approval.request_id)

    with pytest.raises(ValueError, match="not pending"):
        store.approve(approval.request_id, reviewer_id="reviewer-1")
