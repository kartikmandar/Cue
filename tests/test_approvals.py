from datetime import datetime, timedelta, timezone

import pytest

from cue.approvals import ApprovalRequestStore, ApprovalStatus, approval_required
from cue.policy import ApprovalTier, PolicyDecision


def decision(tier):
    return PolicyDecision(
        allowed=tier != ApprovalTier.BLOCKED,
        approval_tier=tier,
        reason=f"{tier.value} decision",
        risk_reasons=[],
        requires_reviewer_approval=tier == ApprovalTier.GUARDIAN_REQUIRED,
        redaction_required=False,
        audit_event_summary="Approval test summary.",
    )


def test_approval_required_matches_approval_tiers():
    assert approval_required(ApprovalTier.INFORM_ONLY) is False
    assert approval_required(ApprovalTier.CONFIRM_EACH_ACTION) is True
    assert approval_required(ApprovalTier.CONFIRM_SENSITIVE) is True
    assert approval_required(ApprovalTier.GUARDIAN_REQUIRED) is True
    assert approval_required(ApprovalTier.BLOCKED) is False


def test_request_and_approve_user_confirmation():
    store = ApprovalRequestStore()

    request = store.request(
        session_id="session-1",
        workflow_id="workflow-1",
        app="TextEdit",
        action_type="type_text",
        policy_decision=decision(ApprovalTier.CONFIRM_EACH_ACTION),
    )
    approved = store.approve(request.request_id, actor="user")

    assert request.status == ApprovalStatus.PENDING
    assert approved.status == ApprovalStatus.APPROVED
    assert approved.actor == "user"
    assert approved.policy_reason == "confirm_each_action decision"


def test_blocked_policy_decision_cannot_create_pending_approval():
    store = ApprovalRequestStore()

    with pytest.raises(ValueError, match="blocked"):
        store.request(
            session_id="session-1",
            workflow_id="workflow-1",
            app="Keychain Access",
            action_type="type_text",
            policy_decision=decision(ApprovalTier.BLOCKED),
        )


def test_approval_store_can_deny_expire_and_cancel_pending_requests():
    now = datetime(2026, 6, 29, tzinfo=timezone.utc)
    store = ApprovalRequestStore(now=lambda: now)

    to_deny = store.request(
        session_id="session-1",
        workflow_id="workflow-deny",
        app="TextEdit",
        action_type="type_text",
        policy_decision=decision(ApprovalTier.CONFIRM_EACH_ACTION),
    )
    to_expire = store.request(
        session_id="session-1",
        workflow_id="workflow-expire",
        app="TextEdit",
        action_type="type_text",
        policy_decision=decision(ApprovalTier.CONFIRM_EACH_ACTION),
        ttl_seconds=1,
    )
    to_cancel = store.request(
        session_id="session-1",
        workflow_id="workflow-cancel",
        app="TextEdit",
        action_type="type_text",
        policy_decision=decision(ApprovalTier.CONFIRM_EACH_ACTION),
    )

    assert store.deny(to_deny.request_id, actor="user").status == ApprovalStatus.DENIED
    store._now = lambda: now + timedelta(seconds=2)
    assert store.expire(to_expire.request_id).status == ApprovalStatus.EXPIRED
    assert store.cancel(to_cancel.request_id).status == ApprovalStatus.CANCELED


def test_cannot_approve_expired_request():
    now = datetime(2026, 6, 29, tzinfo=timezone.utc)
    store = ApprovalRequestStore(now=lambda: now)
    request = store.request(
        session_id="session-1",
        workflow_id="workflow-1",
        app="TextEdit",
        action_type="type_text",
        policy_decision=decision(ApprovalTier.CONFIRM_EACH_ACTION),
        ttl_seconds=1,
    )
    store._now = lambda: now + timedelta(seconds=2)
    store.expire(request.request_id)

    with pytest.raises(ValueError, match="not pending"):
        store.approve(request.request_id, actor="user")
