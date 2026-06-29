from cue.config import Settings
from cue.actions import WorkflowCategory
from cue.policy import ApprovalTier, PolicyDecision, evaluate_policy


def make_settings(**overrides):
    values = {
        "cerebras_api_key": "test-key",
        "allowed_apps": ["TextEdit", "Preview", "Safari", "Terminal", "Finder"],
        "blocked_apps": ["Keychain Access", "1Password", "Blocked Demo"],
        "allowed_domains": ["localhost", "127.0.0.1", "demo.local"],
    }
    values.update(overrides)
    return Settings(**values)


def test_policy_decision_contains_task_2_required_fields():
    decision = PolicyDecision(
        allowed=True,
        approval_tier=ApprovalTier.INFORM_ONLY,
        reason="Screen summary is read-only.",
        risk_reasons=[],
        requires_reviewer_approval=False,
        redaction_required=False,
        audit_event_summary="Read-only screen summary allowed.",
    )

    assert decision.allowed is True
    assert decision.approval_tier == ApprovalTier.INFORM_ONLY
    assert decision.reason == "Screen summary is read-only."
    assert decision.risk_reasons == []
    assert decision.requires_reviewer_approval is False
    assert decision.redaction_required is False
    assert decision.audit_event_summary == "Read-only screen summary allowed."


def test_blocks_password_managers_keychain_and_system_settings():
    settings = make_settings()

    blocked_apps = ["1Password", "Bitwarden", "Keychain Access", "System Settings"]

    for app in blocked_apps:
        decision = evaluate_policy(
            app=app,
            action_type="type_text",
            summary="Open the app and inspect the current item.",
            settings=settings,
        )

        assert decision.allowed is False
        assert decision.approval_tier == ApprovalTier.BLOCKED
        assert any("sensitive app" in reason for reason in decision.risk_reasons)


def test_blocks_banking_payment_and_payroll_contexts():
    settings = make_settings()

    for summary in [
        "Submit payroll changes for the employee.",
        "Open the banking portal and pay the invoice.",
        "Enter the credit card payment.",
    ]:
        decision = evaluate_policy(
            app="Safari",
            action_type="click",
            domain="payroll.example.com",
            summary=summary,
            settings=settings,
        )

        assert decision.allowed is False
        assert decision.approval_tier == ApprovalTier.BLOCKED
        assert any("blocked context" in reason for reason in decision.risk_reasons)


def test_allows_configured_demo_apps_with_confirmation():
    settings = make_settings(allowed_apps=["TextEdit"])

    decision = evaluate_policy(
        app="TextEdit",
        action_type="type_text",
        summary="Type a safe demo title into a local document.",
        settings=settings,
    )

    assert decision.allowed is True
    assert decision.approval_tier == ApprovalTier.CONFIRM_EACH_ACTION
    assert decision.requires_reviewer_approval is False
    assert "TextEdit" in decision.audit_event_summary


def test_terminal_write_is_blocked_unless_enabled():
    blocked = evaluate_policy(
        app="Terminal",
        action_type="type_text",
        summary="Run a shell command in the project.",
        settings=make_settings(allow_terminal_write=False),
    )

    allowed = evaluate_policy(
        app="Terminal",
        action_type="type_text",
        summary="Run a shell command in the project.",
        settings=make_settings(allow_terminal_write=True),
    )

    assert blocked.allowed is False
    assert blocked.approval_tier == ApprovalTier.BLOCKED
    assert any("terminal write" in reason for reason in blocked.risk_reasons)
    assert allowed.allowed is True
    assert allowed.approval_tier == ApprovalTier.CONFIRM_SENSITIVE


def test_terminal_handoff_prompt_can_be_typed_without_enabling_command_execution():
    decision = evaluate_policy(
        app="Terminal",
        action_type="type_text",
        summary=(
            "Type a Claude Code handoff prompt without pressing Return; "
            "do not execute a command."
        ),
        settings=make_settings(allow_terminal_write=False),
    )

    assert decision.allowed is True
    assert decision.approval_tier == ApprovalTier.CONFIRM_SENSITIVE
    assert any("terminal handoff" in reason for reason in decision.risk_reasons)


def test_guardian_required_for_destructive_or_admin_actions():
    settings = make_settings()

    decision = evaluate_policy(
        app="Finder",
        action_type="delete_file",
        summary="Delete the existing project archive.",
        settings=settings,
    )

    assert decision.allowed is True
    assert decision.approval_tier == ApprovalTier.GUARDIAN_REQUIRED
    assert decision.requires_reviewer_approval is True
    assert any("guardian" in reason for reason in decision.risk_reasons)


def test_read_only_actions_are_inform_only_and_sensitive_text_needs_redaction():
    settings = make_settings()

    decision = evaluate_policy(
        app="Preview",
        action_type="none",
        summary="Read visible text for alex@example.com.",
        settings=settings,
    )

    assert decision.allowed is True
    assert decision.approval_tier == ApprovalTier.INFORM_ONLY
    assert decision.redaction_required is True


def test_browser_domain_must_be_allowed_when_domain_state_is_available():
    settings = make_settings(allowed_domains=["localhost", "demo.local"])

    decision = evaluate_policy(
        app="Safari",
        action_type="click",
        domain="unknown.example.com",
        workflow_category=WorkflowCategory.BROWSER,
        summary="Click a safe local demo button.",
        settings=settings,
    )

    assert decision.allowed is False
    assert decision.approval_tier == ApprovalTier.BLOCKED
    assert any("domain" in reason for reason in decision.risk_reasons)


def test_sensitive_workflow_category_blocks_password_contexts_before_action():
    settings = make_settings()

    decision = evaluate_policy(
        app="TextEdit",
        action_type="type_text",
        workflow_category=WorkflowCategory.SENSITIVE,
        summary="Type the password from this page into the form.",
        settings=settings,
    )

    assert decision.allowed is False
    assert decision.approval_tier == ApprovalTier.BLOCKED
    assert decision.redaction_required is True
    assert any("sensitive" in reason for reason in decision.risk_reasons)


def test_yolo_mode_allows_sensitive_and_terminal_actions_without_reviewer_gate():
    settings = make_settings(yolo_mode=True, allow_terminal_write=False)

    decision = evaluate_policy(
        app="Keychain Access",
        action_type="type_text",
        workflow_category=WorkflowCategory.SENSITIVE,
        domain="bank.example.com",
        summary="Type a terminal command into a sensitive app.",
        settings=settings,
    )

    assert decision.allowed is True
    assert decision.approval_tier == ApprovalTier.INFORM_ONLY
    assert decision.requires_reviewer_approval is False
    assert any("YOLO mode" in reason for reason in decision.risk_reasons)
