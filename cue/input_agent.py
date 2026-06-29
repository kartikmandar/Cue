from __future__ import annotations

from typing import Any

from cue.agent_models import NormalizedInput


class InputAgent:
    def normalize(
        self,
        text: str | NormalizedInput,
        *,
        input_mode: str = "text",
        source: str = "command_palette",
        metadata: dict[str, Any] | None = None,
    ) -> NormalizedInput:
        if isinstance(text, NormalizedInput):
            return text

        raw_text = str(text)
        normalized_text = " ".join(raw_text.split())
        if not normalized_text:
            raise ValueError("request text is required")

        return NormalizedInput(
            text=normalized_text,
            raw_text=raw_text,
            input_mode=input_mode,
            source=source,
            metadata=metadata or {},
        )


def normalize_input(
    text: str | NormalizedInput,
    *,
    input_mode: str = "text",
    source: str = "command_palette",
    metadata: dict[str, Any] | None = None,
) -> NormalizedInput:
    return InputAgent().normalize(
        text,
        input_mode=input_mode,
        source=source,
        metadata=metadata,
    )
