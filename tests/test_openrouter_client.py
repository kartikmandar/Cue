from types import SimpleNamespace

from cue.config import Settings
from cue.model_clients import ProviderModelClient
from cue.openrouter_client import OpenRouterClient


def make_settings(**overrides):
    values = {
        "cerebras_api_key": "test-cerebras-key",
        "openrouter_api_key": "test-openrouter-key",
        "openrouter_base_url": "https://openrouter.example/api/v1",
        "openrouter_http_referer": "https://cue.example",
        "openrouter_app_title": "Cue Test",
    }
    values.update(overrides)
    return Settings(**values)


class FakeResponse:
    def __init__(self, payload):
        self.payload = payload
        self.raise_for_status_calls = 0

    def raise_for_status(self):
        self.raise_for_status_calls += 1

    def json(self):
        return self.payload


class FakeHttpClient:
    def __init__(self, response):
        self.response = response
        self.calls = []

    def post(self, url, *, headers, json):
        self.calls.append({"url": url, "headers": headers, "json": json})
        return self.response


class FakeModelClient:
    def __init__(self, result):
        self.result = result
        self.calls = []

    def complete(self, messages, *, response_format=None):
        self.calls.append({"messages": messages, "response_format": response_format})
        return self.result


def clock_from(*values):
    times = list(values)

    def clock():
        return times.pop(0)

    return clock


def test_openrouter_complete_posts_openai_compatible_chat_request():
    response = FakeResponse(
        {
            "id": "generation-1",
            "model": "google/gemma-4-31b-it:free",
            "choices": [{"message": {"content": "Cue is ready."}}],
            "usage": {
                "prompt_tokens": 10,
                "completion_tokens": 5,
                "total_tokens": 15,
            },
            "service_tier": "default",
            "system_fingerprint": "fp-test",
        }
    )
    http_client = FakeHttpClient(response)
    messages = [{"role": "user", "content": "Say ready."}]
    response_format = {"type": "json_object"}

    result = OpenRouterClient(
        settings=make_settings(),
        http_client=http_client,
        clock=clock_from(10.0, 11.08),
    ).complete(messages, response_format=response_format)

    assert http_client.calls == [
        {
            "url": "https://openrouter.example/api/v1/chat/completions",
            "headers": {
                "Authorization": "Bearer test-openrouter-key",
                "Content-Type": "application/json",
                "HTTP-Referer": "https://cue.example",
                "X-Title": "Cue Test",
            },
            "json": {
                "model": "google/gemma-4-31b-it:free",
                "messages": messages,
                "response_format": response_format,
            },
        }
    ]
    assert response.raise_for_status_calls == 1
    assert result.text == "Cue is ready."
    assert result.provider == "openrouter"
    assert result.model == "google/gemma-4-31b-it:free"
    assert result.latency_ms == 1080
    assert result.usage == {
        "prompt_tokens": 10,
        "completion_tokens": 5,
        "total_tokens": 15,
    }
    assert result.time_info == {
        "id": "generation-1",
        "service_tier": "default",
        "system_fingerprint": "fp-test",
    }


def test_openrouter_complete_omits_optional_attribution_headers_when_blank():
    response = FakeResponse(
        {
            "model": "google/gemma-4-31b-it:free",
            "choices": [{"message": {"content": "OK"}}],
        }
    )
    http_client = FakeHttpClient(response)

    OpenRouterClient(
        settings=make_settings(openrouter_http_referer="", openrouter_app_title=""),
        http_client=http_client,
        clock=clock_from(1.0, 1.01),
    ).complete([{"role": "user", "content": "OK?"}])

    headers = http_client.calls[0]["headers"]
    assert "HTTP-Referer" not in headers
    assert "X-Title" not in headers


def test_provider_model_client_routes_to_active_provider():
    openrouter_result = SimpleNamespace(provider="openrouter", text="from router")
    cerebras_result = SimpleNamespace(provider="cerebras", text="from cerebras")
    openrouter = FakeModelClient(openrouter_result)
    cerebras = FakeModelClient(cerebras_result)
    settings = make_settings(model_provider="openrouter")

    result = ProviderModelClient(
        settings=settings,
        clients={"openrouter": openrouter, "cerebras": cerebras},
    ).complete([{"role": "user", "content": "hello"}])

    assert result is openrouter_result
    assert len(openrouter.calls) == 1
    assert cerebras.calls == []
