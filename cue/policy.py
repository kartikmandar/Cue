from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from urllib.parse import urlparse

from cue.actions import WorkflowCategory
from cue.config import Settings
from cue.redaction import contains_sensitive_context, contains_sensitive_text, redact_text


class ApprovalTier(str, Enum):
    INFORM_ONLY = "inform_only"
    CONFIRM_EACH_ACTION = "confirm_each_action"
    CONFIRM_SENSITIVE = "confirm_sensitive"
    GUARDIAN_REQUIRED = "guardian_required"
    BLOCKED = "blocked"


@dataclass(frozen=True)
class PolicyDecision:
    allowed: bool
    approval_tier: ApprovalTier
    reason: str
    risk_reasons: list[str]
    requires_reviewer_approval: bool
    redaction_required: bool
    audit_event_summary: str


_SENSITIVE_APP_KEYWORDS = (
    "1password",
    "bitwarden",
    "dashlane",
    "keeper",
    "keychain",
    "lastpass",
    "password manager",
    "system preferences",
    "system settings",
)
_BLOCKED_CONTEXT_KEYWORDS = (
    "bank",
    "banking",
    "billing portal",
    "credit card",
    "pay invoice",
    "payment",
    "payroll",
)
_GUARDIAN_KEYWORDS = (
    "admin",
    "customer data",
    "delete",
    "destructive",
    "deploy",
    "existing project archive",
    "hr",
    "legal",
    "medical",
    "release",
)
_SENSITIVE_ACTION_KEYWORDS = (
    "edit existing",
    "run command",
    "send",
    "submit",
    "terminal command",
    "upload",
)
_READ_ONLY_ACTIONS = {"none", "verify", "wait_for_window"}
_LOW_RISK_STATE_ACTIONS = {"open_app", "open_file", "activate_app", "type_text"}
_TERMINAL_WRITE_ACTIONS = {
    "click",
    "hotkey",
    "press_key",
    "run_command",
    "set_value",
    "type_text",
}
_DESTRUCTIVE_ACTIONS = {
    "admin",
    "delete",
    "delete_file",
    "deploy",
    "release",
    "remove_file",
}


def _normalized(value: str | None) -> str:
    return (value or "").casefold()


def _matches_any(value: str, candidates: list[str] | tuple[str, ...]) -> bool:
    normalized = _normalized(value)
    return any(candidate.casefold() in normalized for candidate in candidates)


def _workflow_category_value(category: WorkflowCategory | str | None) -> str:
    if isinstance(category, WorkflowCategory):
        return category.value
    return _normalized(category)


def _app_is_configured_blocked(app: str, settings: Settings) -> bool:
    return _matches_any(app, settings.blocked_apps)


def _app_is_sensitive(app: str) -> bool:
    return _matches_any(app, _SENSITIVE_APP_KEYWORDS)


def _context_text(app: str, domain: str | None, summary: str | None) -> str:
    return " ".join(part for part in (app, domain or "", summary or "") if part)


def _domain_host(domain: str | None) -> str:
    if not domain:
        return ""
    raw = domain.strip()
    parsed = urlparse(raw if "://" in raw else f"https://{raw}")
    host = parsed.hostname or raw.split("/", 1)[0]
    return host.casefold()


def _domain_matches(host: str, candidate: str) -> bool:
    allowed = _domain_host(candidate)
    return bool(allowed and (host == allowed or host.endswith(f".{allowed}")))


def _domain_is_allowed(domain: str | None, settings: Settings) -> bool:
    host = _domain_host(domain)
    if not host or not settings.allowed_domains:
        return True
    return any(_domain_matches(host, allowed) for allowed in settings.allowed_domains)


def _domain_is_configured_blocked(domain: str | None, settings: Settings) -> bool:
    blocked_domains = getattr(settings, "blocked_domains", [])
    host = _domain_host(domain)
    if not host or not blocked_domains:
        return False
    return any(_domain_matches(host, blocked) for blocked in blocked_domains)


def _audit_summary(app: str, action_type: str, summary: str | None) -> str:
    safe_summary = redact_text(summary)
    if safe_summary:
        return f"{app}: {action_type} -> {safe_summary}"
    return f"{app}: {action_type}"


def _decision(
    *,
    allowed: bool,
    approval_tier: ApprovalTier,
    reason: str,
    risk_reasons: list[str],
    app: str,
    action_type: str,
    summary: str | None,
) -> PolicyDecision:
    return PolicyDecision(
        allowed=allowed,
        approval_tier=approval_tier,
        reason=reason,
        risk_reasons=risk_reasons,
        requires_reviewer_approval=approval_tier == ApprovalTier.GUARDIAN_REQUIRED,
        redaction_required=contains_sensitive_text(summary)
        or contains_sensitive_context(summary),
        audit_event_summary=_audit_summary(app, action_type, summary),
    )


def evaluate_policy(
    *,
    app: str,
    action_type: str,
    settings: Settings,
    summary: str | None = None,
    domain: str | None = None,
    workflow_category: WorkflowCategory | str | None = None,
) -> PolicyDecision:
    action = _normalized(action_type)
    category = _workflow_category_value(workflow_category)
    context = _context_text(app, domain, summary)
    sensitive_context = contains_sensitive_context(context)

    if _app_is_sensitive(app) or _app_is_configured_blocked(app, settings):
        return _decision(
            allowed=False,
            approval_tier=ApprovalTier.BLOCKED,
            reason="Blocked because the active app is sensitive or denied by policy.",
            risk_reasons=["sensitive app blocked by policy"],
            app=app,
            action_type=action_type,
            summary=summary,
        )

    if category == WorkflowCategory.SENSITIVE.value or sensitive_context:
        return _decision(
            allowed=False,
            approval_tier=ApprovalTier.BLOCKED,
            reason="Blocked because the workflow touches credentials or sensitive auth.",
            risk_reasons=["sensitive workflow blocked by policy"],
            app=app,
            action_type=action_type,
            summary=summary,
        )

    if _matches_any(context, _BLOCKED_CONTEXT_KEYWORDS):
        return _decision(
            allowed=False,
            approval_tier=ApprovalTier.BLOCKED,
            reason="Blocked because the workflow touches banking, payment, or payroll.",
            risk_reasons=["blocked context: banking/payment/payroll"],
            app=app,
            action_type=action_type,
            summary=summary,
        )

    if _domain_is_configured_blocked(domain, settings):
        return _decision(
            allowed=False,
            approval_tier=ApprovalTier.BLOCKED,
            reason="Blocked because the current browser domain is denied by policy.",
            risk_reasons=["domain denied by policy"],
            app=app,
            action_type=action_type,
            summary=summary,
        )

    browser_category = category in {
        WorkflowCategory.BROWSER.value,
        WorkflowCategory.PDF.value,
    }
    browser_app = _matches_any(app, ("safari", "chrome", "browser"))
    if domain and (browser_category or browser_app) and not _domain_is_allowed(
        domain, settings
    ):
        return _decision(
            allowed=False,
            approval_tier=ApprovalTier.BLOCKED,
            reason="Blocked because the current browser domain is not allowlisted.",
            risk_reasons=["domain not allowlisted"],
            app=app,
            action_type=action_type,
            summary=summary,
        )

    if _normalized(app) == "terminal" and action in _TERMINAL_WRITE_ACTIONS:
        if not settings.allow_terminal_write:
            return _decision(
                allowed=False,
                approval_tier=ApprovalTier.BLOCKED,
                reason="Blocked because terminal write actions are disabled.",
                risk_reasons=["terminal write blocked unless explicitly enabled"],
                app=app,
                action_type=action_type,
                summary=summary,
            )
        return _decision(
            allowed=True,
            approval_tier=ApprovalTier.CONFIRM_SENSITIVE,
            reason="Terminal write is enabled and requires stronger confirmation.",
            risk_reasons=["terminal write requires sensitive confirmation"],
            app=app,
            action_type=action_type,
            summary=summary,
        )

    if (
        app
        and _normalized(app) != "unknown"
        and settings.allowed_apps
        and not _matches_any(app, settings.allowed_apps)
        and action not in _READ_ONLY_ACTIONS
    ):
        return _decision(
            allowed=False,
            approval_tier=ApprovalTier.BLOCKED,
            reason="Blocked because the target app is not allowlisted.",
            risk_reasons=["app not allowlisted"],
            app=app,
            action_type=action_type,
            summary=summary,
        )

    if action in _DESTRUCTIVE_ACTIONS or _matches_any(context, _GUARDIAN_KEYWORDS):
        return _decision(
            allowed=True,
            approval_tier=ApprovalTier.GUARDIAN_REQUIRED,
            reason="Guardian approval is required for this high-risk workflow.",
            risk_reasons=["guardian required for high-risk action"],
            app=app,
            action_type=action_type,
            summary=summary,
        )

    if action in _READ_ONLY_ACTIONS:
        return _decision(
            allowed=True,
            approval_tier=ApprovalTier.INFORM_ONLY,
            reason="Read-only action is allowed without action approval.",
            risk_reasons=[],
            app=app,
            action_type=action_type,
            summary=summary,
        )

    if _matches_any(f"{action_type} {summary or ''}", _SENSITIVE_ACTION_KEYWORDS):
        return _decision(
            allowed=True,
            approval_tier=ApprovalTier.CONFIRM_SENSITIVE,
            reason="Sensitive state-changing action requires stronger confirmation.",
            risk_reasons=["sensitive action requires confirmation"],
            app=app,
            action_type=action_type,
            summary=summary,
        )

    risk_reasons = []
    if settings.allowed_apps and not _matches_any(app, settings.allowed_apps):
        risk_reasons.append("app is not configured as a demo app")

    if action in _LOW_RISK_STATE_ACTIONS or action:
        return _decision(
            allowed=True,
            approval_tier=ApprovalTier.CONFIRM_EACH_ACTION,
            reason="Configured desktop action requires user confirmation.",
            risk_reasons=risk_reasons,
            app=app,
            action_type=action_type,
            summary=summary,
        )

    return _decision(
        allowed=True,
        approval_tier=ApprovalTier.INFORM_ONLY,
        reason="No state-changing action requested.",
        risk_reasons=risk_reasons,
        app=app,
        action_type=action_type,
        summary=summary,
    )
