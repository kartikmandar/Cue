from __future__ import annotations

from collections.abc import Callable
import subprocess
from typing import Any


Runner = Callable[..., subprocess.CompletedProcess[str] | Any]


def speak(
    text: str,
    enabled: bool = True,
    *,
    runner: Runner | None = None,
) -> None:
    """Print narration and optionally send it to macOS speech output."""
    print(text)
    if not enabled or not text.strip():
        return

    run = runner or subprocess.run
    try:
        run(
            ["say"],
            input=text,
            text=True,
            check=False,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except (OSError, subprocess.SubprocessError):
        return
