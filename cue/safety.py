from __future__ import annotations

from dataclasses import dataclass, field
import json
from pathlib import Path
from typing import Any, Mapping
from urllib.parse import urlparse

from cue.actions import ActionType
from cue.agent_models import WorkflowPlan, WorkflowStep
from cue.audit import record_audit_event
from cue.config import Settings
from cue.policy import ApprovalTier, PolicyDecision, evaluate_policy
from cue.redaction import (
    contains_sensitive_context,
    contains_sensitive_text,
    redact_for_persistence,
)


@dataclass(frozen=True)
class FocusSnapshot:
    active_app: str
    active_window: str | None = None
    focused_element: str | None = None
    domain: str | None = None


@dataclass(frozen=True)
class SafetyDecision:
    allowed: bool
    approval_tier: ApprovalTier
    reason: str
    risk_reasons: list[str]
    requires_reviewer_approval: bool = False
    redaction_required: bool = False
    audit_event_summary: str = ""
    requires_reobservation: bool = False
    requires_renewed_confirmation: bool = False
    screenshot_allowed: bool = True
    action_allowed: bool = True
    policy_decisions: list[PolicyDecision] = field(default_factory=list)


_TIER_ORDER = {
    ApprovalTier.INFORM_ONLY: 0,
    ApprovalTier.CONFIRM_EACH_ACTION: 1,
    ApprovalTier.CONFIRM_SENSITIVE: 2,
    ApprovalTier.GUARDIAN_REQUIRED: 3,
    ApprovalTier.BLOCKED: 4,
}
_DESTRUCTIVE_KEYWORDS = (
    "delete",
    "deleted",
    "destructive",
    "erase",
    "remove",
    "removed",
    "rm -rf",
    "trash",
)
_SENSITIVE_APP_KEYWORDS = (
    "1password",
    "bitwarden",
    "dashlane",
    "keeper",
    "keychain",
    "lastpass",
    "password manager",
    "system settings",
)


def evaluate_workflow_plan(
    plan: WorkflowPlan,
    *,
    settings: Settings,
    observation: FocusSnapshot | Mapping[str, Any] | None = None,
) -> SafetyDecision:
    snapshot = _coerce_snapshot(observation)
    summary = _plan_summary(plan)
    if _plan_is_destructive_multi_step(plan):
        return SafetyDecision(
            allowed=False,
            action_allowed=False,
            approval_tier=ApprovalTier.BLOCKED,
            reason="Blocked because destructive multi-step workflows are not allowed.",
            risk_reasons=["destructive multi-step workflow blocked by policy"],
            redaction_required=_redaction_required(summary),
            audit_event_summary=redact_for_persistence(summary),
        )

    decisions = [
        evaluate_policy(
            app=_step_app(step, snapshot),
            action_type=step.action.action_type.value,
            domain=_step_domain(step, snapshot),
            workflow_category=plan.workflow_category,
            summary=_step_summary(step, plan),
            settings=settings,
        )
        for step in plan.steps
    ]

    if not decisions:
        decisions = [
            evaluate_policy(
                app=snapshot.active_app if snapshot else "Unknown",
                action_type=ActionType.NONE.value,
                domain=snapshot.domain if snapshot else None,
                workflow_category=plan.workflow_category,
                summary=summary,
                settings=settings,
            )
        ]

    return _combine_policy_decisions(
        decisions,
        fallback_summary=summary,
        blocked_reason="Blocked by policy before workflow preview.",
        allowed_reason="Workflow passed policy before preview.",
    )


def evaluate_step_before_execution(
    step: WorkflowStep,
    *,
    settings: Settings,
    preview_decision: SafetyDecision,
    preview_snapshot: FocusSnapshot | Mapping[str, Any] | None,
    current_snapshot: FocusSnapshot | Mapping[str, Any] | None,
) -> SafetyDecision:
    preview = _coerce_snapshot(preview_snapshot)
    current = _coerce_snapshot(current_snapshot)
    if current and _screenshot_blocked_for_app(current.active_app, settings):
        return SafetyDecision(
            allowed=False,
            action_allowed=False,
            approval_tier=ApprovalTier.BLOCKED,
            reason="Blocked because a sensitive app is active.",
            risk_reasons=["sensitive app blocks screenshots and actions"],
            redaction_required=True,
            audit_event_summary=redact_for_persistence(_step_summary(step)),
            screenshot_allowed=False,
        )

    if settings.focus_check_required and _focus_drifted(preview, current):
        return SafetyDecision(
            allowed=False,
            action_allowed=False,
            approval_tier=preview_decision.approval_tier,
            reason="Focus drift requires re-observation and renewed confirmation.",
            risk_reasons=["focus drift detected before execution"],
            redaction_required=preview_decision.redaction_required,
            audit_event_summary=preview_decision.audit_event_summary,
            requires_reobservation=True,
            requires_renewed_confirmation=True,
            screenshot_allowed=True,
        )

    policy = evaluate_policy(
        app=_step_app(step, current),
        action_type=step.action.action_type.value,
        domain=current.domain if current else None,
        summary=_step_summary(step),
        settings=settings,
    )
    if not policy.allowed:
        return _blocked_from_policy(
            policy,
            reason="Blocked by policy before step execution.",
            screenshot_allowed=True,
        )

    if _tier_value(policy.approval_tier) > _tier_value(preview_decision.approval_tier):
        return SafetyDecision(
            allowed=False,
            action_allowed=False,
            approval_tier=policy.approval_tier,
            reason="Step risk escalated and needs renewed approval.",
            risk_reasons=[*policy.risk_reasons, "risk escalated before execution"],
            requires_reviewer_approval=policy.requires_reviewer_approval,
            redaction_required=policy.redaction_required,
            audit_event_summary=policy.audit_event_summary,
            requires_renewed_confirmation=True,
            screenshot_allowed=True,
            policy_decisions=[policy],
        )

    return SafetyDecision(
        allowed=True,
        action_allowed=True,
        approval_tier=policy.approval_tier,
        reason="Step passed policy before execution.",
        risk_reasons=policy.risk_reasons,
        requires_reviewer_approval=policy.requires_reviewer_approval,
        redaction_required=policy.redaction_required,
        audit_event_summary=policy.audit_event_summary,
        screenshot_allowed=True,
        policy_decisions=[policy],
    )


def record_safety_audit_event(
    path: str | Path,
    *,
    event_type: str,
    session_id: str,
    workflow_id: str,
    app: str,
    action_type: str,
    decision: SafetyDecision,
    summary: str,
    verification_status: str = "not_started",
    latency_ms: int = 0,
) -> dict[str, Any]:
    return record_audit_event(
        path,
        event_type=event_type,
        session_id=session_id,
        workflow_id=workflow_id,
        app=app,
        action_type=action_type,
        approval_tier=decision.approval_tier,
        policy_reason=decision.reason,
        verification_status=verification_status,
        latency_ms=latency_ms,
        summary=summary,
    )


def _combine_policy_decisions(
    decisions: list[PolicyDecision],
    *,
    fallback_summary: str,
    blocked_reason: str,
    allowed_reason: str,
) -> SafetyDecision:
    blocked = [decision for decision in decisions if not decision.allowed]
    if blocked:
        tier = ApprovalTier.BLOCKED
        risks = _unique(reason for decision in blocked for reason in decision.risk_reasons)
        return SafetyDecision(
            allowed=False,
            action_allowed=False,
            approval_tier=tier,
            reason=blocked_reason,
            risk_reasons=risks,
            requires_reviewer_approval=False,
            redaction_required=any(decision.redaction_required for decision in decisions),
            audit_event_summary=redact_for_persistence(
                " | ".join(decision.audit_event_summary for decision in blocked)
                or fallback_summary
            ),
            policy_decisions=decisions,
        )

    tier = max(
        (decision.approval_tier for decision in decisions),
        key=_tier_value,
        default=ApprovalTier.INFORM_ONLY,
    )
    return SafetyDecision(
        allowed=True,
        action_allowed=True,
        approval_tier=tier,
        reason=allowed_reason,
        risk_reasons=_unique(
            reason for decision in decisions for reason in decision.risk_reasons
        ),
        requires_reviewer_approval=any(
            decision.requires_reviewer_approval for decision in decisions
        ),
        redaction_required=any(decision.redaction_required for decision in decisions),
        audit_event_summary=redact_for_persistence(
            " | ".join(decision.audit_event_summary for decision in decisions)
            or fallback_summary
        ),
        policy_decisions=decisions,
    )


def _blocked_from_policy(
    policy: PolicyDecision,
    *,
    reason: str,
    screenshot_allowed: bool,
) -> SafetyDecision:
    return SafetyDecision(
        allowed=False,
        action_allowed=False,
        approval_tier=policy.approval_tier,
        reason=reason,
        risk_reasons=policy.risk_reasons,
        requires_reviewer_approval=policy.requires_reviewer_approval,
        redaction_required=policy.redaction_required,
        audit_event_summary=policy.audit_event_summary,
        screenshot_allowed=screenshot_allowed,
        policy_decisions=[policy],
    )


def _coerce_snapshot(
    value: FocusSnapshot | Mapping[str, Any] | None,
) -> FocusSnapshot | None:
    if value is None:
        return None
    if isinstance(value, FocusSnapshot):
        return value
    return FocusSnapshot(
        active_app=str(value.get("active_app") or value.get("app") or "Unknown"),
        active_window=value.get("active_window") or value.get("window"),
        focused_element=value.get("focused_element") or value.get("focus"),
        domain=value.get("domain"),
    )


def _step_app(step: WorkflowStep, snapshot: FocusSnapshot | None) -> str:
    action = step.action
    for key in ("app_name", "target_app", "app"):
        value = action.payload.get(key)
        if value:
            return str(value)
    if action.expected_app:
        return action.expected_app
    if snapshot:
        return snapshot.active_app
    return "Unknown"


def _step_domain(step: WorkflowStep, snapshot: FocusSnapshot | None) -> str | None:
    for key in ("domain", "host"):
        value = step.action.payload.get(key)
        if value:
            return str(value)
    url = step.action.payload.get("url")
    if url:
        parsed = urlparse(str(url))
        return parsed.hostname or str(url)
    return snapshot.domain if snapshot else None


def _plan_summary(plan: WorkflowPlan) -> str:
    parts = [
        plan.intent.normalized_input.text,
        plan.narration,
        plan.confirmation_prompt,
        plan.expected_outcome,
        " ".join(plan.risk_reasons),
    ]
    parts.extend(_step_summary(step, plan) for step in plan.steps)
    return " | ".join(part for part in parts if part)


def _step_summary(step: WorkflowStep, plan: WorkflowPlan | None = None) -> str:
    payload_text = _payload_summary(step.action.payload)
    parts = [
        plan.workflow_category.value if plan else "",
        step.title,
        step.action.reason,
        step.expected_outcome,
        step.verification_criteria or "",
        payload_text,
    ]
    return " | ".join(part for part in parts if part)


def _payload_summary(payload: Mapping[str, Any]) -> str:
    if not payload:
        return ""
    return json.dumps(payload, sort_keys=True, default=str)


def _plan_is_destructive_multi_step(plan: WorkflowPlan) -> bool:
    return len(plan.steps) > 1 and any(_step_is_destructive(step) for step in plan.steps)


def _step_is_destructive(step: WorkflowStep) -> bool:
    text = _step_summary(step).casefold()
    return any(keyword in text for keyword in _DESTRUCTIVE_KEYWORDS)


def _redaction_required(text: str | None) -> bool:
    return contains_sensitive_text(text) or contains_sensitive_context(text)


def _screenshot_blocked_for_app(app: str, settings: Settings) -> bool:
    if not settings.block_screenshots_for_sensitive_apps:
        return False
    app_value = app.casefold()
    blocked_by_name = any(keyword in app_value for keyword in _SENSITIVE_APP_KEYWORDS)
    blocked_by_settings = any(
        configured.casefold() in app_value for configured in settings.blocked_apps
    )
    return blocked_by_name or blocked_by_settings


def _focus_drifted(
    preview: FocusSnapshot | None,
    current: FocusSnapshot | None,
) -> bool:
    if not preview or not current:
        return False
    return (
        _norm(preview.active_app) != _norm(current.active_app)
        or _norm(preview.active_window) != _norm(current.active_window)
        or _norm(preview.focused_element) != _norm(current.focused_element)
    )


def _tier_value(tier: ApprovalTier | str) -> int:
    return _TIER_ORDER[ApprovalTier(tier)]


def _norm(value: str | None) -> str:
    return (value or "").casefold()


def _unique(values: Any) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        if value and value not in seen:
            seen.add(value)
            result.append(value)
    return result
