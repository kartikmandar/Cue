from __future__ import annotations

import os
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field

import pytest
from cerebras.cloud.sdk import APIStatusError, RateLimitError

from cue.cerebras_client import CerebrasClient
from cue.config import Settings, load_settings


RUN_FLAG = "CUE_RUN_LIVE_CEREBRAS_THROTTLE_TEST"
REQUEST_BUDGET_ENV = "CUE_CEREBRAS_THROTTLE_REQUESTS"
CONCURRENCY_ENV = "CUE_CEREBRAS_THROTTLE_CONCURRENCY"
DEFAULT_REQUEST_BUDGET = 256
DEFAULT_CONCURRENCY = 32

MESSAGES = [
    {"role": "system", "content": "Reply with exactly OK and nothing else."},
    {"role": "user", "content": "Throttle probe."},
]


@dataclass(frozen=True)
class ProbeResult:
    attempt: int
    status: str
    latency_ms: int
    text: str = ""
    error: str = ""
    retry_after: str | None = None


@dataclass
class ThrottleSummary:
    attempts: list[ProbeResult] = field(default_factory=list)

    @property
    def successes(self) -> list[ProbeResult]:
        return [result for result in self.attempts if result.status == "success"]

    @property
    def rate_limits(self) -> list[ProbeResult]:
        return [result for result in self.attempts if result.status == "rate_limited"]

    @property
    def unexpected_errors(self) -> list[ProbeResult]:
        return [result for result in self.attempts if result.status == "error"]

    def diagnostic(self) -> str:
        first_rate_limit = self.rate_limits[0] if self.rate_limits else None
        first_error = self.unexpected_errors[0] if self.unexpected_errors else None
        details = [
            f"attempts={len(self.attempts)}",
            f"successes={len(self.successes)}",
            f"rate_limits={len(self.rate_limits)}",
            f"unexpected_errors={len(self.unexpected_errors)}",
        ]
        if first_rate_limit:
            details.append(
                "first_rate_limit="
                f"attempt:{first_rate_limit.attempt},"
                f"retry_after:{first_rate_limit.retry_after},"
                f"error:{first_rate_limit.error}"
            )
        if first_error:
            details.append(
                "first_unexpected_error="
                f"attempt:{first_error.attempt},error:{first_error.error}"
            )
        return "; ".join(details)


def test_cerebras_live_strict_throttle_proves_real_rate_limit():
    if os.getenv(RUN_FLAG, "").strip().lower() not in {"1", "true", "yes", "on"}:
        pytest.skip(f"Set {RUN_FLAG}=true to run this live Cerebras throttle test.")

    settings = load_settings()
    request_budget = _env_int(REQUEST_BUDGET_ENV, DEFAULT_REQUEST_BUDGET)
    concurrency = _env_int(CONCURRENCY_ENV, DEFAULT_CONCURRENCY)
    assert request_budget > 0, f"{REQUEST_BUDGET_ENV} must be greater than zero"
    assert concurrency > 0, f"{CONCURRENCY_ENV} must be greater than zero"
    concurrency = min(concurrency, request_budget)

    warmup = CerebrasClient(settings=settings).complete(MESSAGES)
    assert warmup.text.strip() == "OK"
    assert warmup.usage.get("total_tokens", 0) > 0

    summary = _run_throttle_probe(
        settings=settings,
        request_budget=request_budget,
        concurrency=concurrency,
    )

    print(summary.diagnostic())
    assert not summary.unexpected_errors, summary.diagnostic()
    assert summary.rate_limits, (
        "Strict throttle proof failed: Cerebras did not return a 429/rate-limit "
        f"signal within {request_budget} requests at concurrency {concurrency}. "
        f"{summary.diagnostic()}"
    )


def _run_throttle_probe(
    *,
    settings: Settings,
    request_budget: int,
    concurrency: int,
) -> ThrottleSummary:
    summary = ThrottleSummary()
    next_attempt = 1

    with ThreadPoolExecutor(max_workers=concurrency) as executor:
        while next_attempt <= request_budget and not summary.rate_limits:
            batch_size = min(concurrency, request_budget - next_attempt + 1)
            futures = [
                executor.submit(_probe_once, settings, attempt)
                for attempt in range(next_attempt, next_attempt + batch_size)
            ]
            next_attempt += batch_size

            for future in as_completed(futures):
                result = future.result()
                summary.attempts.append(result)

    return summary


def _probe_once(settings: Settings, attempt: int) -> ProbeResult:
    started_at = time.perf_counter()
    try:
        result = CerebrasClient(settings=settings).complete(MESSAGES)
    except Exception as exc:  # noqa: BLE001 - this live probe classifies SDK errors.
        latency_ms = int(round((time.perf_counter() - started_at) * 1000))
        if _is_rate_limit(exc):
            return ProbeResult(
                attempt=attempt,
                status="rate_limited",
                latency_ms=latency_ms,
                error=_error_summary(exc),
                retry_after=_retry_after(exc),
            )
        return ProbeResult(
            attempt=attempt,
            status="error",
            latency_ms=latency_ms,
            error=_error_summary(exc),
        )

    text = result.text.strip()
    if text != "OK":
        return ProbeResult(
            attempt=attempt,
            status="error",
            latency_ms=result.latency_ms,
            text=text,
            error=f"Expected OK response, got {text!r}",
        )
    return ProbeResult(
        attempt=attempt,
        status="success",
        latency_ms=result.latency_ms,
        text=text,
    )


def _is_rate_limit(exc: Exception) -> bool:
    status_code = getattr(exc, "status_code", None)
    if isinstance(exc, RateLimitError) or status_code == 429:
        return True
    if isinstance(exc, APIStatusError):
        return getattr(exc, "status_code", None) == 429
    return (
        "rate limit" in str(exc).casefold()
        or "too many requests" in str(exc).casefold()
    )


def _retry_after(exc: Exception) -> str | None:
    headers = getattr(exc, "headers", None)
    if headers is None:
        response = getattr(exc, "response", None)
        headers = getattr(response, "headers", None)
    if headers is None:
        return None
    getter = getattr(headers, "get", None)
    if getter is None:
        return None
    retry_after = getter("retry-after") or getter("Retry-After")
    return str(retry_after) if retry_after is not None else None


def _error_summary(exc: Exception) -> str:
    status_code = getattr(exc, "status_code", None)
    prefix = f"{type(exc).__name__}"
    if status_code is not None:
        prefix = f"{prefix}(status_code={status_code})"
    return f"{prefix}: {str(exc)}"


def _env_int(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None:
        return default
    return int(raw.strip())
