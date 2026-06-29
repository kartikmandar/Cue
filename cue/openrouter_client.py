from __future__ import annotations

import time
from collections.abc import Callable, Mapping, Sequence
from typing import Any

import httpx

from cue.config import Settings, load_settings
from cue.model_clients import Message, ModelResult, ResponseFormat


class OpenRouterClient:
    def __init__(
        self,
        *,
        settings: Settings | None = None,
        http_client: Any | None = None,
        clock: Callable[[], float] = time.perf_counter,
    ) -> None:
        self.settings = settings or load_settings()
        self.http_client = http_client or httpx.Client(
            timeout=self.settings.cerebras_sdk_timeout_seconds,
        )
        self._clock = clock

    def complete(
        self,
        messages: Sequence[Message],
        *,
        response_format: ResponseFormat | None = None,
    ) -> ModelResult:
        if not self.settings.openrouter_api_key:
            raise RuntimeError("OPENROUTER_API_KEY is required for OpenRouter mode")

        payload: dict[str, Any] = {
            "model": self.settings.openrouter_model,
            "messages": list(messages),
        }
        if response_format is not None:
            payload["response_format"] = dict(response_format)

        started_at = self._clock()
        response = self.http_client.post(
            f"{self.settings.openrouter_base_url}/chat/completions",
            headers=_headers(self.settings),
            json=payload,
        )
        response.raise_for_status()
        data = response.json()
        finished_at = self._clock()

        return ModelResult(
            text=_extract_text(data),
            latency_ms=int(round((finished_at - started_at) * 1000)),
            usage=_as_dict(data.get("usage")),
            time_info=_time_info(data),
            provider="openrouter",
            model=str(data.get("model") or self.settings.openrouter_model),
        )


def _headers(settings: Settings) -> dict[str, str]:
    headers = {
        "Authorization": f"Bearer {settings.openrouter_api_key}",
        "Content-Type": "application/json",
    }
    if settings.openrouter_http_referer:
        headers["HTTP-Referer"] = settings.openrouter_http_referer
    if settings.openrouter_app_title:
        headers["X-Title"] = settings.openrouter_app_title
    return headers


def _extract_text(response: Mapping[str, Any]) -> str:
    choices = response.get("choices") or []
    if not choices:
        return ""
    message = _get(choices[0], "message", {})
    content = _get(message, "content")
    if content is None:
        return ""
    if isinstance(content, str):
        return content
    return str(content)


def _time_info(response: Mapping[str, Any]) -> dict[str, Any]:
    keys = (
        "id",
        "service_tier",
        "system_fingerprint",
        "openrouter_metadata",
    )
    return {key: response[key] for key in keys if response.get(key) is not None}


def _get(value: Any, key: str, default: Any = None) -> Any:
    if isinstance(value, Mapping):
        return value.get(key, default)
    return getattr(value, key, default)


def _as_dict(value: Any) -> dict[str, Any]:
    if value is None:
        return {}
    if isinstance(value, Mapping):
        return dict(value)
    return {
        key: item
        for key, item in vars(value).items()
        if not key.startswith("_") and item is not None
    }
