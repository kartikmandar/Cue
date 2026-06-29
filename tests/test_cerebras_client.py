from types import SimpleNamespace

from cue.cerebras_client import CerebrasClient, CerebrasResult
from cue.config import Settings


def make_settings(**overrides):
    values = {"cerebras_api_key": "test-key"}
    values.update(overrides)
    return Settings(**values)


class FakeCompletions:
    def __init__(self, response):
        self.response = response
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        return self.response


class FakeSdkClient:
    def __init__(self, response):
        self.completions = FakeCompletions(response)
        self.chat = SimpleNamespace(completions=self.completions)


def fake_response(
    *,
    text="Cue is ready.",
    usage=None,
    time_info=None,
):
    return SimpleNamespace(
        choices=[
            SimpleNamespace(
                message=SimpleNamespace(content=text),
            )
        ],
        usage=usage
        or SimpleNamespace(
            prompt_tokens=11,
            completion_tokens=7,
            total_tokens=18,
        ),
        time_info=time_info
        or SimpleNamespace(
            queue_time=0.001,
            prompt_time=0.004,
            completion_time=0.015,
            total_time=0.020,
        ),
    )


def clock_from(*values):
    times = list(values)

    def clock():
        return times.pop(0)

    return clock


def test_complete_sends_model_id_and_messages_to_sdk():
    response = fake_response()
    sdk_client = FakeSdkClient(response)
    messages = [
        {"role": "system", "content": "You are Cue."},
        {"role": "user", "content": "What is on screen?"},
    ]

    CerebrasClient(
        settings=make_settings(),
        sdk_client=sdk_client,
        clock=clock_from(10.0, 10.125),
    ).complete(messages)

    assert sdk_client.completions.calls == [
        {
            "model": "gemma-4-31b",
            "messages": messages,
        }
    ]


def test_complete_passes_response_format_when_provided():
    response = fake_response()
    sdk_client = FakeSdkClient(response)
    response_format = {
        "type": "json_schema",
        "json_schema": {
            "name": "screen_summary",
            "schema": {
                "type": "object",
                "properties": {"summary": {"type": "string"}},
                "required": ["summary"],
            },
        },
    }

    CerebrasClient(
        settings=make_settings(),
        sdk_client=sdk_client,
        clock=clock_from(1.0, 1.010),
    ).complete(
        [{"role": "user", "content": "Return JSON."}],
        response_format=response_format,
    )

    assert sdk_client.completions.calls[0]["response_format"] == response_format


def test_reasoning_effort_is_omitted_when_configured_as_none():
    response = fake_response()
    sdk_client = FakeSdkClient(response)

    CerebrasClient(
        settings=make_settings(cerebras_reasoning_effort="none"),
        sdk_client=sdk_client,
        clock=clock_from(1.0, 1.001),
    ).complete([{"role": "user", "content": "Fast path."}])

    assert "reasoning_effort" not in sdk_client.completions.calls[0]


def test_reasoning_effort_is_included_when_not_none():
    response = fake_response()
    sdk_client = FakeSdkClient(response)

    CerebrasClient(
        settings=make_settings(cerebras_reasoning_effort="low"),
        sdk_client=sdk_client,
        clock=clock_from(1.0, 1.001),
    ).complete([{"role": "user", "content": "Think lightly."}])

    assert sdk_client.completions.calls[0]["reasoning_effort"] == "low"


def test_complete_returns_text_latency_usage_and_time_info():
    response = fake_response(
        text='{"summary": "TextEdit is active."}',
        usage=SimpleNamespace(
            prompt_tokens=21,
            completion_tokens=9,
            total_tokens=30,
        ),
        time_info=SimpleNamespace(
            queue_time=0.003,
            prompt_time=0.010,
            completion_time=0.031,
            total_time=0.044,
        ),
    )
    sdk_client = FakeSdkClient(response)

    result = CerebrasClient(
        settings=make_settings(),
        sdk_client=sdk_client,
        clock=clock_from(42.000, 42.250),
    ).complete([{"role": "user", "content": "Summarize."}])

    assert result == CerebrasResult(
        text='{"summary": "TextEdit is active."}',
        latency_ms=250,
        usage={
            "prompt_tokens": 21,
            "completion_tokens": 9,
            "total_tokens": 30,
        },
        time_info={
            "queue_time": 0.003,
            "prompt_time": 0.010,
            "completion_time": 0.031,
            "total_time": 0.044,
        },
    )


def test_default_sdk_client_uses_settings_api_key_and_timeout(monkeypatch):
    created = {}
    response = fake_response()

    class FakeCerebras:
        def __init__(self, **kwargs):
            created.update(kwargs)
            self.completions = FakeCompletions(response)
            self.chat = SimpleNamespace(completions=self.completions)

    monkeypatch.setattr("cue.cerebras_client.Cerebras", FakeCerebras)

    CerebrasClient(settings=make_settings(cerebras_sdk_timeout_seconds=12))

    assert created == {"api_key": "test-key", "timeout": 12}
