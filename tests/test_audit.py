import json

from cue.audit import AuditEvent, append_audit_event
from cue.policy import ApprovalTier


def test_appends_redacted_jsonl_audit_event(tmp_path):
    log_path = tmp_path / "audit.jsonl"
    event = AuditEvent(
        event_type="policy_decision",
        session_id="session-1",
        workflow_id="workflow-1",
        app="TextEdit",
        action_type="type_text",
        approval_tier=ApprovalTier.CONFIRM_EACH_ACTION,
        policy_reason="Allowed demo app.",
        verification_status="not_started",
        latency_ms=42,
        summary="Draft for alex@example.com with key sk-cb-1234567890abcdef.",
    )

    written = append_audit_event(log_path, event)

    lines = log_path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1
    record = json.loads(lines[0])
    assert record == written
    assert record["event_type"] == "policy_decision"
    assert record["session_id"] == "session-1"
    assert record["workflow_id"] == "workflow-1"
    assert record["app"] == "TextEdit"
    assert record["action_type"] == "type_text"
    assert record["approval_tier"] == "confirm_each_action"
    assert record["policy_reason"] == "Allowed demo app."
    assert record["verification_status"] == "not_started"
    assert record["latency_ms"] == 42
    assert record["summary"] == (
        "Draft for [REDACTED_EMAIL] with key [REDACTED_API_KEY]."
    )


def test_audit_event_never_persists_raw_sensitive_payloads(tmp_path):
    log_path = tmp_path / ".cue" / "audit.jsonl"
    event = AuditEvent(
        event_type="execution",
        session_id="session-2",
        workflow_id="workflow-2",
        app="Preview",
        action_type="none",
        approval_tier=ApprovalTier.INFORM_ONLY,
        policy_reason="Read-only.",
        verification_status="passed",
        latency_ms=0,
        summary=(
            "prompt: summarize this full document. raw_screenshot=/tmp/private.png "
            "email alex@example.com password: swordfish"
        ),
    )

    append_audit_event(log_path, event)

    raw_log = log_path.read_text(encoding="utf-8")
    record = json.loads(raw_log)
    assert "alex@example.com" not in raw_log
    assert "swordfish" not in raw_log
    assert "raw_screenshot" not in record
    assert "prompt" not in record
    assert set(record) >= {
        "event_type",
        "session_id",
        "workflow_id",
        "app",
        "action_type",
        "approval_tier",
        "policy_reason",
        "verification_status",
        "latency_ms",
        "summary",
    }
