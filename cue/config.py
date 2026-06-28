from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv


@dataclass(frozen=True)
class Settings:
    cerebras_api_key: str
    cerebras_model: str = "gemma-4-31b"
    cerebras_reasoning_effort: str = "none"
    cerebras_sdk_timeout_seconds: int = 30
    confirm_actions: bool = True
    save_screenshots: bool = False
    speak: bool = True
    max_actions_per_turn: int = 1


def _env_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def load_settings() -> Settings:
    load_dotenv()
    api_key = os.getenv("CEREBRAS_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError("CEREBRAS_API_KEY is required")

    return Settings(
        cerebras_api_key=api_key,
        cerebras_model=os.getenv("CEREBRAS_MODEL", "gemma-4-31b"),
        cerebras_reasoning_effort=os.getenv("CEREBRAS_REASONING_EFFORT", "none"),
        cerebras_sdk_timeout_seconds=int(
            os.getenv("CEREBRAS_SDK_TIMEOUT_SECONDS", "30")
        ),
        confirm_actions=_env_bool("CUE_CONFIRM_ACTIONS", True),
        save_screenshots=_env_bool("CUE_SAVE_SCREENSHOTS", False),
        speak=_env_bool("CUE_SPEAK", True),
        max_actions_per_turn=int(os.getenv("CUE_MAX_ACTIONS_PER_TURN", "1")),
    )
