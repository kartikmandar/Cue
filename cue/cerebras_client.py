from __future__ import annotations

import time
from collections.abc import Callable, Mapping, Sequence
from typing import Any

from cerebras.cloud.sdk import Cerebras

from cue.config import Settings, load_settings
from cue.model_clients import Message, ModelResult, ResponseFormat


CerebrasResult = ModelResult


class CerebrasClient:
    def __init__(
        self,
        *,
        settings: Settings | None = None,
        sdk_client: Any | None = None,
        clock: Callable[[], float] = time.perf_counter,
    ) -> None:
        self.settings = settings or load_settings()
        self.sdk_client = sdk_client or Cerebras(
            api_key=self.settings.cerebras_api_key,
            timeout=self.settings.cerebras_sdk_timeout_seconds,
        )
        self._clock = clock

    def complete(
        self,
        messages: Sequence[Message],
        *,
        response_format: ResponseFormat | None = None,
    ) -> CerebrasResult:
        started_at = self._clock()
        kwargs: dict[str, Any] = {
            "model": self.settings.cerebras_model,
            "messages": messages,
        }

        if response_format is not None:
            kwargs["response_format"] = response_format

        reasoning_effort = self.settings.cerebras_reasoning_effort.strip().lower()
        if reasoning_effort and reasoning_effort != "none":
            kwargs["reasoning_effort"] = reasoning_effort

        response = self.sdk_client.chat.completions.create(**kwargs)
        finished_at = self._clock()

        return CerebrasResult(
            text=_extract_text(response),
            latency_ms=int(round((finished_at - started_at) * 1000)),
            usage=_as_dict(_get(response, "usage")),
            time_info=_as_dict(_get(response, "time_info")),
            provider="cerebras",
            model=self.settings.cerebras_model,
        )


def _extract_text(response: Any) -> str:
    choices = _get(response, "choices", []) or []
    if not choices:
        return ""

    message = _get(choices[0], "message", {})
    content = _get(message, "content")
    if content is None:
        return ""
    if isinstance(content, str):
        return content
    return str(content)


def _get(value: Any, key: str, default: Any = None) -> Any:
    if isinstance(value, Mapping):
        return value.get(key, default)
    return getattr(value, key, default)


def _as_dict(value: Any) -> dict[str, Any]:
    if value is None:
        return {}
    if isinstance(value, Mapping):
        return dict(value)
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="json", exclude_none=True)
    return {
        key: item
        for key, item in vars(value).items()
        if not key.startswith("_") and item is not None
    }
