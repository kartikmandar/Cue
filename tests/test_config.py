import pytest

from cue.config import load_settings


def test_requires_cerebras_api_key(monkeypatch):
    monkeypatch.delenv("CEREBRAS_API_KEY", raising=False)
    with pytest.raises(RuntimeError, match="CEREBRAS_API_KEY"):
        load_settings()


def test_loads_defaults(monkeypatch):
    monkeypatch.setenv("CEREBRAS_API_KEY", "test-key")
    settings = load_settings()
    assert settings.cerebras_model == "gemma-4-31b"
    assert settings.cerebras_sdk_timeout_seconds == 30
    assert settings.confirm_actions is True
    assert settings.max_actions_per_turn == 1
