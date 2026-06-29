from __future__ import annotations

import time
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any, Protocol

from cue.config import Settings, load_settings


Message = Mapping[str, Any]
ResponseFormat = Mapping[str, Any]


@dataclass(frozen=True)
class ModelResult:
    text: str
    latency_ms: int
    usage: dict[str, Any]
    time_info: dict[str, Any]
    provider: str = "cerebras"
    model: str = "gemma-4-31b"


class ModelClient(Protocol):
    def complete(
        self,
        messages: Sequence[Message],
        *,
        response_format: ResponseFormat | None = None,
    ) -> ModelResult: ...


class ProviderModelClient:
    def __init__(
        self,
        *,
        settings: Settings | None = None,
        settings_getter: Callable[[], Settings] | None = None,
        clients: Mapping[str, ModelClient] | None = None,
        clock: Callable[[], float] = time.perf_counter,
    ) -> None:
        self.settings = settings or load_settings()
        self._settings_getter = settings_getter
        self._clients = dict(clients or {})
        self._clock = clock

    def complete(
        self,
        messages: Sequence[Message],
        *,
        response_format: ResponseFormat | None = None,
    ) -> ModelResult:
        settings = self._active_settings()
        return self._client_for(settings).complete(
            messages,
            response_format=response_format,
        )

    def _active_settings(self) -> Settings:
        if self._settings_getter is not None:
            return self._settings_getter()
        return self.settings

    def _client_for(self, settings: Settings) -> ModelClient:
        if settings.model_provider in self._clients:
            return self._clients[settings.model_provider]
        if settings.model_provider == "openrouter":
            from cue.openrouter_client import OpenRouterClient

            client = OpenRouterClient(settings=settings, clock=self._clock)
        else:
            from cue.cerebras_client import CerebrasClient

            client = CerebrasClient(settings=settings, clock=self._clock)
        self._clients[settings.model_provider] = client
        return client
