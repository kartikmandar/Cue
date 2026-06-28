import pytest

from cue.config import load_settings


CONFIG_ENV_KEYS = [
    "CEREBRAS_MODEL",
    "CEREBRAS_REASONING_EFFORT",
    "CEREBRAS_SDK_TIMEOUT_SECONDS",
    "CUE_API_HOST",
    "CUE_API_PORT",
    "CUE_BACKEND_MODE",
    "CUE_PRIVACY_MODE",
    "CUE_CONFIRM_ACTIONS",
    "CUE_APPROVAL_TIER",
    "CUE_HIGH_RISK_APPROVAL",
    "CUE_REVIEWER_MODE",
    "CUE_SAVE_SCREENSHOTS",
    "CUE_BLOCK_SCREENSHOTS_FOR_SENSITIVE_APPS",
    "CUE_AUDIT_LOG",
    "CUE_AUDIT_LOG_REDACTED",
    "CUE_AUDIT_LOG_PATH",
    "CUE_SESSION_STATE_PATH",
    "CUE_MEMORY_ENABLED",
    "CUE_MAX_WORKFLOW_STEPS",
    "CUE_MAX_ACTIONS_PER_STEP",
    "CUE_REQUIRE_WORKFLOW_APPROVAL",
    "CUE_VERIFY_AFTER_EACH_ACTION",
    "CUE_FOCUS_CHECK_REQUIRED",
    "CUE_REPORT_CURSOR_AND_FOCUS",
    "CUE_ALLOW_APP_LAUNCH",
    "CUE_ALLOW_BROWSER_NAVIGATION",
    "CUE_ALLOW_DOCUMENT_EDITING",
    "CUE_ALLOW_TERMINAL_READONLY",
    "CUE_ALLOW_TERMINAL_WRITE",
    "CUE_ENABLE_VOICE_INPUT",
    "CUE_SPEAK",
    "CUE_ALLOWED_APPS",
    "CUE_BLOCKED_APPS",
    "CUE_ALLOWED_DOMAINS",
]


def clear_config_env(monkeypatch):
    for key in CONFIG_ENV_KEYS:
        monkeypatch.delenv(key, raising=False)


def test_requires_cerebras_api_key(monkeypatch):
    clear_config_env(monkeypatch)
    monkeypatch.delenv("CEREBRAS_API_KEY", raising=False)
    with pytest.raises(RuntimeError, match="CEREBRAS_API_KEY"):
        load_settings(env_file=None)


def test_default_model_is_gemma_4(monkeypatch):
    clear_config_env(monkeypatch)
    monkeypatch.setenv("CEREBRAS_API_KEY", "test-key")
    settings = load_settings(env_file=None)

    assert settings.cerebras_model == "gemma-4-31b"


def test_strict_privacy_defaults(monkeypatch):
    clear_config_env(monkeypatch)
    monkeypatch.setenv("CEREBRAS_API_KEY", "test-key")
    settings = load_settings(env_file=None)

    assert settings.privacy_mode == "strict"
    assert settings.save_screenshots is False
    assert settings.audit_log_redacted is True
    assert settings.allow_terminal_write is False
    assert settings.require_workflow_approval is True
    assert settings.focus_check_required is True


def test_comma_separated_policy_lists_parse_into_lists(monkeypatch):
    clear_config_env(monkeypatch)
    monkeypatch.setenv("CEREBRAS_API_KEY", "test-key")
    monkeypatch.setenv("CUE_ALLOWED_APPS", "TextEdit, Preview,Google Chrome")
    monkeypatch.setenv("CUE_BLOCKED_APPS", "Keychain Access, 1Password")
    monkeypatch.setenv("CUE_ALLOWED_DOMAINS", "localhost, 127.0.0.1,example.test")

    settings = load_settings(env_file=None)

    assert settings.allowed_apps == ["TextEdit", "Preview", "Google Chrome"]
    assert settings.blocked_apps == ["Keychain Access", "1Password"]
    assert settings.allowed_domains == ["localhost", "127.0.0.1", "example.test"]
