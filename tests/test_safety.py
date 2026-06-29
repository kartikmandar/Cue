import json

from cue.actions import ActionType, CueAction, WorkflowCategory
from cue.agent_models import IntentResult, NormalizedInput, WorkflowPlan, WorkflowStep
from cue.config import Settings
from cue.policy import ApprovalTier
from cue.safety import (
    FocusSnapshot,
    evaluate_step_before_execution,
    evaluate_workflow_plan,
    record_safety_audit_event,
)


def make_settings(**overrides):
    values = {
        "cerebras_api_key": "test-key",
        "allowed_apps": ["TextEdit", "Preview", "Safari", "Google Chrome", "Terminal", "Finder"],
        "blocked_apps": ["Keychain Access", "1Password", "Bitwarden", "System Settings"],
        "allowed_domains": ["localhost", "127.0.0.1", "demo.local"],
    }
    values.update(overrides)
    return Settings(**values)


def make_intent(category):
    normalized = NormalizedInput(
        text="Open TextEdit and type Cue",
        raw_text="Open TextEdit and type Cue",
        input_mode="text",
        source="test",
    )
    return IntentResult(
        normalized_input=normalized,
        intent=category.value,
        workflow_required=category != WorkflowCategory.ANSWER,
        workflow_category=category,
        risk_level="low",
        reason="test intent",
    )


def make_step(
    step_id,
    action_type,
    *,
    expected_app="TextEdit",
    expected_window=None,
    expected_focus=None,
    payload=None,
    reason=None,
    outcome=None,
):
    return WorkflowStep(
        step_id=step_id,
        title=step_id.replace("-", " ").title(),
        action=CueAction(
            action_type=action_type,
            payload=payload or {},
            reason=reason or f"Perform {action_type.value}.",
            expected_app=expected_app,
            expected_window=expected_window,
            expected_focus=expected_focus,
            changes_state=action_type
            not in {ActionType.NONE, ActionType.VERIFY, ActionType.WAIT_FOR_WINDOW},
        ),
        expected_outcome=outcome or f"{step_id} completed.",
        verification_criteria=outcome or f"{step_id} completed.",
    )


def make_plan(category=WorkflowCategory.DOCUMENT, steps=None, **overrides):
    values = {
        "intent": make_intent(category),
        "narration": "I will preview a safe workflow.",
        "workflow_required": category != WorkflowCategory.ANSWER,
        "workflow_category": category,
        "steps": steps or [],
        "risk_level": "low",
        "approval_tier": ApprovalTier.CONFIRM_EACH_ACTION,
        "confirmation_prompt": "Approve this workflow?",
        "expected_outcome": "The requested task is visible and verified.",
        "risk_reasons": [],
        "requires_reviewer_approval": False,
        "redaction_applied": False,
        "allowed_by_policy": True,
        "policy_reason": "Allowed for test.",
        "audit_event_summary": "Workflow previewed.",
        "workflow_id": "workflow-7",
    }
    values.update(overrides)
    return WorkflowPlan(**values)


def snapshot(app="TextEdit", window="Untitled", focus="body", domain=None):
    return FocusSnapshot(
        active_app=app,
        active_window=window,
        focused_element=focus,
        domain=domain,
    )


def test_blocks_destructive_multi_step_flow_before_preview():
    plan = make_plan(
        WorkflowCategory.DESKTOP,
        steps=[
            make_step("step-1", ActionType.OPEN_APP, expected_app="Finder", payload={"app_name": "Finder"}),
            make_step(
                "step-2",
                ActionType.HOTKEY,
                expected_app="Finder",
                payload={"keys": ["command", "delete"]},
                reason="Delete the existing project archive.",
                outcome="The selected project archive is deleted.",
            ),
        ],
    )

    decision = evaluate_workflow_plan(
        plan,
        settings=make_settings(),
        observation=snapshot(app="Finder", window="Downloads"),
    )

    assert decision.allowed is False
    assert decision.action_allowed is False
    assert decision.approval_tier == ApprovalTier.BLOCKED
    assert any("destructive multi-step" in reason for reason in decision.risk_reasons)


def test_allows_low_risk_app_launch_before_preview():
    plan = make_plan(
        WorkflowCategory.APP_LAUNCH,
        steps=[
            make_step(
                "step-1",
                ActionType.OPEN_APP,
                expected_app="TextEdit",
                payload={"app_name": "TextEdit"},
                outcome="TextEdit is active.",
            )
        ],
    )

    decision = evaluate_workflow_plan(
        plan,
        settings=make_settings(),
        observation=snapshot(app="Finder", window="Desktop"),
    )

    assert decision.allowed is True
    assert decision.action_allowed is True
    assert decision.approval_tier == ApprovalTier.CONFIRM_EACH_ACTION
    assert decision.requires_reviewer_approval is False


def test_allows_textedit_workflow_before_preview():
    plan = make_plan(
        WorkflowCategory.DOCUMENT,
        steps=[
            make_step("step-1", ActionType.OPEN_APP, payload={"app_name": "TextEdit"}),
            make_step("step-2", ActionType.TYPE_TEXT, payload={"text": "Cue"}, outcome="Cue is typed."),
            make_step("step-3", ActionType.VERIFY, outcome="The title Cue is visible."),
        ],
    )

    decision = evaluate_workflow_plan(
        plan,
        settings=make_settings(),
        observation=snapshot(app="TextEdit", window="Untitled"),
    )

    assert decision.allowed is True
    assert decision.approval_tier == ApprovalTier.CONFIRM_EACH_ACTION
    assert "TextEdit" in decision.audit_event_summary


def test_blocks_password_context_before_preview():
    plan = make_plan(
        WorkflowCategory.SENSITIVE,
        steps=[
            make_step(
                "step-1",
                ActionType.TYPE_TEXT,
                payload={"text": "password from this page"},
                reason="Type the password from this page.",
                outcome="The password is entered.",
            )
        ],
    )

    decision = evaluate_workflow_plan(
        plan,
        settings=make_settings(),
        observation=snapshot(app="Safari", window="Sign in", domain="demo.local"),
    )

    assert decision.allowed is False
    assert decision.approval_tier == ApprovalTier.BLOCKED
    assert decision.redaction_required is True
    assert any("sensitive" in reason for reason in decision.risk_reasons)


def test_terminal_write_is_blocked_by_default_before_preview():
    plan = make_plan(
        WorkflowCategory.TERMINAL,
        steps=[
            make_step(
                "step-1",
                ActionType.TYPE_TEXT,
                expected_app="Terminal",
                payload={"text": "rm -rf ."},
                reason="Run a shell command.",
            )
        ],
    )

    decision = evaluate_workflow_plan(
        plan,
        settings=make_settings(allow_terminal_write=False),
        observation=snapshot(app="Terminal", window="zsh"),
    )

    assert decision.allowed is False
    assert decision.approval_tier == ApprovalTier.BLOCKED
    assert any("terminal write" in reason for reason in decision.risk_reasons)


def test_focus_drift_requires_reobservation_and_renewed_confirmation():
    plan = make_plan(
        WorkflowCategory.DOCUMENT,
        steps=[make_step("step-1", ActionType.TYPE_TEXT, payload={"text": "Cue"})],
    )
    preview_decision = evaluate_workflow_plan(
        plan,
        settings=make_settings(),
        observation=snapshot(app="TextEdit", window="Untitled", focus="body"),
    )

    decision = evaluate_step_before_execution(
        plan.steps[0],
        settings=make_settings(),
        preview_decision=preview_decision,
        preview_snapshot=snapshot(app="TextEdit", window="Untitled", focus="body"),
        current_snapshot=snapshot(app="Safari", window="Dashboard", focus="search", domain="demo.local"),
    )

    assert decision.allowed is False
    assert decision.action_allowed is False
    assert decision.requires_reobservation is True
    assert decision.requires_renewed_confirmation is True
    assert any("focus drift" in reason for reason in decision.risk_reasons)


def test_sensitive_apps_block_screenshots_and_actions_before_execution():
    plan = make_plan(
        WorkflowCategory.DOCUMENT,
        steps=[make_step("step-1", ActionType.TYPE_TEXT, payload={"text": "Cue"})],
    )
    preview_decision = evaluate_workflow_plan(
        plan,
        settings=make_settings(),
        observation=snapshot(app="TextEdit"),
    )

    decision = evaluate_step_before_execution(
        plan.steps[0],
        settings=make_settings(),
        preview_decision=preview_decision,
        preview_snapshot=snapshot(app="TextEdit"),
        current_snapshot=snapshot(app="Keychain Access", window="Passwords", focus="password table"),
    )

    assert decision.allowed is False
    assert decision.action_allowed is False
    assert decision.screenshot_allowed is False
    assert decision.approval_tier == ApprovalTier.BLOCKED
    assert any("sensitive app" in reason for reason in decision.risk_reasons)


def test_step_risk_escalation_pauses_for_renewed_approval():
    plan = make_plan(
        WorkflowCategory.TERMINAL,
        steps=[
            make_step(
                "step-1",
                ActionType.TYPE_TEXT,
                expected_app="Terminal",
                payload={"text": "echo safe"},
                reason="Type a terminal command.",
            )
        ],
    )
    preview_decision = evaluate_workflow_plan(
        make_plan(
            WorkflowCategory.APP_LAUNCH,
            steps=[make_step("step-0", ActionType.OPEN_APP, expected_app="Terminal", payload={"app_name": "Terminal"})],
        ),
        settings=make_settings(allow_terminal_write=True),
        observation=snapshot(app="Terminal", window="zsh"),
    )

    decision = evaluate_step_before_execution(
        plan.steps[0],
        settings=make_settings(allow_terminal_write=True),
        preview_decision=preview_decision,
        preview_snapshot=snapshot(app="Terminal", window="zsh", focus="prompt"),
        current_snapshot=snapshot(app="Terminal", window="zsh", focus="prompt"),
    )

    assert preview_decision.approval_tier == ApprovalTier.CONFIRM_EACH_ACTION
    assert decision.allowed is False
    assert decision.action_allowed is False
    assert decision.approval_tier == ApprovalTier.CONFIRM_SENSITIVE
    assert decision.requires_renewed_confirmation is True
    assert any("risk escalated" in reason for reason in decision.risk_reasons)


def test_records_redacted_safety_audit_event(tmp_path):
    plan = make_plan(
        WorkflowCategory.DOCUMENT,
        steps=[make_step("step-1", ActionType.TYPE_TEXT, payload={"text": "Cue"})],
    )
    decision = evaluate_workflow_plan(
        plan,
        settings=make_settings(),
        observation=snapshot(app="TextEdit"),
    )

    record = record_safety_audit_event(
        tmp_path / "audit.jsonl",
        event_type="preview",
        session_id="session-7",
        workflow_id="workflow-7",
        app="TextEdit",
        action_type="type_text",
        decision=decision,
        summary="prompt: email alex@example.com password: swordfish",
    )

    raw_log = (tmp_path / "audit.jsonl").read_text(encoding="utf-8")
    assert json.loads(raw_log) == record
    assert "alex@example.com" not in raw_log
    assert "swordfish" not in raw_log
    assert record["event_type"] == "preview"
