from __future__ import annotations

import re


_BEARER_TOKEN_RE = re.compile(r"\bBearer\s+[A-Za-z0-9._~+/=-]{8,}", re.IGNORECASE)
_API_KEY_ASSIGNMENT_RE = re.compile(
    r"\b(?:[A-Z0-9_]*API[_-]?KEY|api[_-]?key|secret|token)\s*[:=]\s*"
    r"['\"]?[A-Za-z0-9][A-Za-z0-9._~+/=-]{11,}['\"]?",
    re.IGNORECASE,
)
_API_KEY_VALUE_RE = re.compile(
    r"\b(?:sk|pk|cb|ck|ghp|gho|xox[baprs])[-_]"
    r"[A-Za-z0-9][A-Za-z0-9._-]{11,}\b",
    re.IGNORECASE,
)
_EMAIL_RE = re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.IGNORECASE)
_SECRET_LABEL_RE = re.compile(
    r"\b(password|passcode|mfa(?:\s+code)?|otp|2fa|verification\s+code)"
    r"\s*[:=]\s*['\"]?\S+['\"]?",
    re.IGNORECASE,
)
_LONG_DIGITS_RE = re.compile(r"\b(?:\d[ -]?){12,}\d?\b")
_ACCOUNT_ASSIGNMENT_RE = re.compile(
    r"\b(?:account|acct|customer|user)[_-]?id\s*[:=]\s*"
    r"['\"]?[A-Za-z0-9][A-Za-z0-9._-]{5,}['\"]?",
    re.IGNORECASE,
)
_ACCOUNT_ID_RE = re.compile(
    r"\b(?:acct|account|customer|user)[_-][A-Za-z0-9]{6,}\b",
    re.IGNORECASE,
)


def _redact_secret_label(match: re.Match[str]) -> str:
    label = " ".join(match.group(1).split())
    return f"{label}: [REDACTED_SECRET]"


def redact_text(text: str | None) -> str:
    if not text:
        return ""

    redacted = str(text)
    redacted = _BEARER_TOKEN_RE.sub("[REDACTED_BEARER_TOKEN]", redacted)
    redacted = _API_KEY_ASSIGNMENT_RE.sub("[REDACTED_API_KEY]", redacted)
    redacted = _API_KEY_VALUE_RE.sub("[REDACTED_API_KEY]", redacted)
    redacted = _EMAIL_RE.sub("[REDACTED_EMAIL]", redacted)
    redacted = _SECRET_LABEL_RE.sub(_redact_secret_label, redacted)
    redacted = _LONG_DIGITS_RE.sub("[REDACTED_NUMBER]", redacted)
    redacted = _ACCOUNT_ASSIGNMENT_RE.sub("[REDACTED_ACCOUNT_ID]", redacted)
    redacted = _ACCOUNT_ID_RE.sub("[REDACTED_ACCOUNT_ID]", redacted)
    return redacted


def contains_sensitive_text(text: str | None) -> bool:
    if not text:
        return False

    value = str(text)
    return any(
        pattern.search(value)
        for pattern in (
            _BEARER_TOKEN_RE,
            _API_KEY_ASSIGNMENT_RE,
            _API_KEY_VALUE_RE,
            _EMAIL_RE,
            _SECRET_LABEL_RE,
            _LONG_DIGITS_RE,
            _ACCOUNT_ASSIGNMENT_RE,
            _ACCOUNT_ID_RE,
        )
    )
