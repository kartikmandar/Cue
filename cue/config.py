from __future__ import annotations

import os
from pathlib import Path
from typing import Literal

from dotenv import load_dotenv
from pydantic import BaseModel, ConfigDict, Field


DEFAULT_ALLOWED_APPS = [
    "TextEdit",
    "Preview",
    "Safari",
    "Google Chrome",
    "Terminal",
    "Finder",
    "Notes",
]
DEFAULT_BLOCKED_APPS = [
    "Keychain Access",
    "1Password",
    "Bitwarden",
    "System Settings",
]
DEFAULT_ALLOWED_DOMAINS = ["localhost", "127.0.0.1"]


class Settings(BaseModel):
    model_config = ConfigDict(frozen=True)

    cerebras_api_key: str
    cerebras_model: str = "gemma-4-31b"
    cerebras_reasoning_effort: str = "none"
    cerebras_sdk_timeout_seconds: int = 30
    openrouter_api_key: str = ""
    openrouter_model: str = "google/gemma-4-31b-it:free"
    openrouter_base_url: str = "https://openrouter.ai/api/v1"
    openrouter_http_referer: str = ""
    openrouter_app_title: str = "Cue"
    model_provider: Literal["cerebras", "openrouter"] = "cerebras"
    api_host: str = "127.0.0.1"
    api_port: int = 8765
    backend_mode: str = "local"
    privacy_mode: str = "strict"
    confirm_actions: bool = True
    approval_tier: str = "confirm_each_action"
    high_risk_approval: str = "guardian"
    reviewer_mode: bool = False
    save_screenshots: bool = False
    block_screenshots_for_sensitive_apps: bool = True
    audit_log: bool = True
    audit_log_redacted: bool = True
    audit_log_path: str = ".cue/audit.jsonl"
    session_state_path: str = ".cue/session.json"
    memory_enabled: bool = True
    max_workflow_steps: int = 5
    max_actions_per_step: int = 1
    require_workflow_approval: bool = True
    verify_after_each_action: bool = True
    focus_check_required: bool = True
    report_cursor_and_focus: bool = True
    allow_app_launch: bool = True
    allow_browser_navigation: bool = True
    allow_document_editing: bool = True
    allow_terminal_readonly: bool = True
    allow_terminal_write: bool = False
    enable_voice_input: bool = False
    speak: bool = True
    yolo_mode: bool = False
    allowed_apps: list[str] = Field(default_factory=lambda: DEFAULT_ALLOWED_APPS.copy())
    blocked_apps: list[str] = Field(default_factory=lambda: DEFAULT_BLOCKED_APPS.copy())
    allowed_domains: list[str] = Field(
        default_factory=lambda: DEFAULT_ALLOWED_DOMAINS.copy()
    )


def _env_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    normalized = raw.strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    raise ValueError(f"{name} must be a boolean value")


def _env_int(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None:
        return default
    return int(raw.strip())


def _env_list(name: str, default: list[str]) -> list[str]:
    raw = os.getenv(name)
    if raw is None:
        return default.copy()
    return [item.strip() for item in raw.split(",") if item.strip()]


def load_settings(env_file: str | Path | None = ".env") -> Settings:
    if env_file is not None:
        load_dotenv(env_file, override=False)

    api_key = os.getenv("CEREBRAS_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError("CEREBRAS_API_KEY is required")

    return Settings(
        cerebras_api_key=api_key,
        cerebras_model=os.getenv("CEREBRAS_MODEL", "gemma-4-31b"),
        cerebras_reasoning_effort=os.getenv("CEREBRAS_REASONING_EFFORT", "none"),
        cerebras_sdk_timeout_seconds=_env_int("CEREBRAS_SDK_TIMEOUT_SECONDS", 30),
        openrouter_api_key=os.getenv("OPENROUTER_API_KEY", "").strip(),
        openrouter_model=os.getenv(
            "OPENROUTER_MODEL",
            "google/gemma-4-31b-it:free",
        ),
        openrouter_base_url=os.getenv(
            "OPENROUTER_BASE_URL",
            "https://openrouter.ai/api/v1",
        ).rstrip("/"),
        openrouter_http_referer=os.getenv("OPENROUTER_HTTP_REFERER", "").strip(),
        openrouter_app_title=os.getenv("OPENROUTER_APP_TITLE", "Cue"),
        model_provider=os.getenv("CUE_MODEL_PROVIDER", "cerebras"),
        api_host=os.getenv("CUE_API_HOST", "127.0.0.1"),
        api_port=_env_int("CUE_API_PORT", 8765),
        backend_mode=os.getenv("CUE_BACKEND_MODE", "local"),
        privacy_mode=os.getenv("CUE_PRIVACY_MODE", "strict"),
        confirm_actions=_env_bool("CUE_CONFIRM_ACTIONS", True),
        approval_tier=os.getenv("CUE_APPROVAL_TIER", "confirm_each_action"),
        high_risk_approval=os.getenv("CUE_HIGH_RISK_APPROVAL", "guardian"),
        reviewer_mode=_env_bool("CUE_REVIEWER_MODE", False),
        save_screenshots=_env_bool("CUE_SAVE_SCREENSHOTS", False),
        block_screenshots_for_sensitive_apps=_env_bool(
            "CUE_BLOCK_SCREENSHOTS_FOR_SENSITIVE_APPS", True
        ),
        audit_log=_env_bool("CUE_AUDIT_LOG", True),
        audit_log_redacted=_env_bool("CUE_AUDIT_LOG_REDACTED", True),
        audit_log_path=os.getenv("CUE_AUDIT_LOG_PATH", ".cue/audit.jsonl"),
        session_state_path=os.getenv("CUE_SESSION_STATE_PATH", ".cue/session.json"),
        memory_enabled=_env_bool("CUE_MEMORY_ENABLED", True),
        max_workflow_steps=_env_int("CUE_MAX_WORKFLOW_STEPS", 5),
        max_actions_per_step=_env_int("CUE_MAX_ACTIONS_PER_STEP", 1),
        require_workflow_approval=_env_bool("CUE_REQUIRE_WORKFLOW_APPROVAL", True),
        verify_after_each_action=_env_bool("CUE_VERIFY_AFTER_EACH_ACTION", True),
        focus_check_required=_env_bool("CUE_FOCUS_CHECK_REQUIRED", True),
        report_cursor_and_focus=_env_bool("CUE_REPORT_CURSOR_AND_FOCUS", True),
        allow_app_launch=_env_bool("CUE_ALLOW_APP_LAUNCH", True),
        allow_browser_navigation=_env_bool("CUE_ALLOW_BROWSER_NAVIGATION", True),
        allow_document_editing=_env_bool("CUE_ALLOW_DOCUMENT_EDITING", True),
        allow_terminal_readonly=_env_bool("CUE_ALLOW_TERMINAL_READONLY", True),
        allow_terminal_write=_env_bool("CUE_ALLOW_TERMINAL_WRITE", False),
        enable_voice_input=_env_bool("CUE_ENABLE_VOICE_INPUT", False),
        speak=_env_bool("CUE_SPEAK", True),
        yolo_mode=_env_bool("CUE_YOLO_MODE", False),
        allowed_apps=_env_list("CUE_ALLOWED_APPS", DEFAULT_ALLOWED_APPS),
        blocked_apps=_env_list("CUE_BLOCKED_APPS", DEFAULT_BLOCKED_APPS),
        allowed_domains=_env_list("CUE_ALLOWED_DOMAINS", DEFAULT_ALLOWED_DOMAINS),
    )
