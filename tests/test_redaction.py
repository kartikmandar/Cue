from cue.redaction import contains_sensitive_text, redact_text


def test_redacts_api_keys_bearer_tokens_and_emails_deterministically():
    text = (
        "CEREBRAS_API_KEY=sk-cb-1234567890abcdef1234567890abcdef "
        "Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.token "
        "email alex@example.com"
    )

    first = redact_text(text)
    second = redact_text(text)

    assert first == second
    assert "sk-cb-1234567890abcdef1234567890abcdef" not in first
    assert "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.token" not in first
    assert "alex@example.com" not in first
    assert "[REDACTED_API_KEY]" in first
    assert "[REDACTED_BEARER_TOKEN]" in first
    assert "[REDACTED_EMAIL]" in first


def test_redacts_password_mfa_labels_and_long_digit_sequences():
    text = (
        "password: hunter2 MFA code=123456 "
        "card number 4111 1111 1111 1111 account id acct_ABC123456789"
    )

    redacted = redact_text(text)

    assert "hunter2" not in redacted
    assert "123456" not in redacted
    assert "4111 1111 1111 1111" not in redacted
    assert "acct_ABC123456789" not in redacted
    assert "[REDACTED_SECRET]" in redacted
    assert "[REDACTED_NUMBER]" in redacted
    assert "[REDACTED_ACCOUNT_ID]" in redacted


def test_contains_sensitive_text_detects_values_before_redaction():
    assert contains_sensitive_text("Use bearer token Bearer abcdefghijklmnop") is True
    assert contains_sensitive_text("Reach me at alex@example.com") is True
    assert contains_sensitive_text("This is a safe local demo title.") is False
