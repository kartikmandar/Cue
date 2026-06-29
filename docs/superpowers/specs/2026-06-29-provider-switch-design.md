# Provider Switch Design

## Context

Cue currently runs a local FastAPI backend with a SwiftUI/AppKit app. The app
already has a top-bar YOLO toggle backed by backend `/mode` endpoints, and the
backend exposes `/health`, `/chat`, `/session/preview`, session control routes,
and audit events. Recent committed work also made YOLO mode a runtime backend
setting and propagated it to existing session orchestrators.

The provider switch should follow that live shape instead of adding a separate
configuration path. The worktree was clean before this spec was written, with
latest commit `2c4d312 Add YOLO mode toggle`.

## Goal

Add a runtime provider switch that routes normal Cue chat and workflow planning
model calls through either Cerebras or OpenRouter, then displays the selected
provider, model, latency, tokens, and backend timing in the existing app timing
surface.

## Provider Contract

Cue supports two provider values:

- `cerebras`: uses the existing official Cerebras SDK wrapper and default model
  `gemma-4-31b`.
- `openrouter`: uses OpenRouter's OpenAI-compatible chat-completions HTTP API
  and default model `google/gemma-4-31b-it:free`.

Backend environment variables:

- `CEREBRAS_API_KEY`: required for the Cerebras provider.
- `CEREBRAS_MODEL`: defaults to `gemma-4-31b`.
- `CEREBRAS_REASONING_EFFORT`: defaults to `none`.
- `OPENROUTER_API_KEY`: required only when selecting the OpenRouter provider.
- `OPENROUTER_MODEL`: defaults to `google/gemma-4-31b-it:free`.
- `OPENROUTER_BASE_URL`: defaults to `https://openrouter.ai/api/v1`.
- `OPENROUTER_HTTP_REFERER`: optional app attribution header.
- `OPENROUTER_APP_TITLE`: optional app attribution header, defaults to `Cue`.
- `CUE_MODEL_PROVIDER`: startup default provider, defaults to `cerebras`.

Swift never receives or stores API keys. It only receives provider/model status
and sends provider selection requests to the local backend.

## Architecture

Introduce a provider-neutral model client surface in Python:

```python
@dataclass(frozen=True)
class ModelResult:
    text: str
    provider: str
    model: str
    latency_ms: int
    usage: dict[str, Any]
    time_info: dict[str, Any]

class ModelClient(Protocol):
    def complete(
        self,
        messages: Sequence[Message],
        *,
        response_format: ResponseFormat | None = None,
    ) -> ModelResult: ...
```

`CerebrasClient` will continue to use the SDK but return `ModelResult`.
`OpenRouterClient` will use `httpx.Client` against
`{OPENROUTER_BASE_URL}/chat/completions` with `Authorization: Bearer ...`,
`Content-Type: application/json`, and optional app attribution headers.

`WorkflowPlanner` will stop constructing a hard-coded `CerebrasClient`. It will
accept a provider-aware client factory or router that reads `settings.model_provider`
at call time. This matters because changing provider in `/mode` should affect
the next `/chat` or `/session/preview` request without restarting the backend.

## Backend API

Extend existing mode endpoints rather than creating a separate provider route:

```json
GET /mode
{
  "yolo_mode": false,
  "model_provider": "cerebras",
  "model": "gemma-4-31b"
}
```

```json
POST /mode
{
  "yolo_mode": false,
  "model_provider": "openrouter"
}
```

The backend returns the active provider and model from `/health` as well, so the
app can sync state on launch. Invalid provider values return a 422 from Pydantic
validation. Selecting OpenRouter without `OPENROUTER_API_KEY` should be allowed
as a mode change only if it fails clearly on the first OpenRouter model call, or
blocked during mode change with a human-readable 400. The implementation should
prefer blocking mode change so the app can revert the segmented control
immediately.

When provider changes, `CueBackend` updates:

- `self.settings`
- planner settings/client routing
- existing session orchestrator settings

The provider change does not mutate old session payloads. The next model-backed
preview/chat call uses the new provider.

## Timing Payload

Extend `timing` objects:

```json
{
  "provider": "openrouter",
  "model": "google/gemma-4-31b-it:free",
  "latency_ms": 1080,
  "token_usage": 35,
  "backend_ms": 1112,
  "provider_timing": {
    "service_tier": "default"
  }
}
```

`provider_timing` is a dictionary for provider-specific metadata. For Cerebras,
copy the existing `time_info`. For OpenRouter, include useful top-level
metadata when present, such as `service_tier`, `system_fingerprint`, or
`openrouter_metadata`. The existing Timing UI should show provider and model,
then latency/tokens/backend timing. It can avoid rendering the full
provider-specific dictionary in the first slice.

## Swift UI

Add a segmented provider picker near the existing top-bar YOLO and Speech
controls:

- `Cerebras`
- `OpenRouter`

The picker should use the same optimistic-update-and-revert pattern as
`setYoloMode`. It calls `setMode(yoloMode:modelProvider:)`, receives a
`CueModeResponse`, and refreshes `appState.modelProvider` plus current provider
label. The details/timing rail displays provider and model for the last
session.

The control is not a benchmark-only toy. It changes the provider used by normal
chat and workflow preview calls.

## Error Handling

Mode selection failures:

- Revert the Swift picker to the previous provider.
- Set `lastErrorMessage` from the backend/client error.
- Do not clear the conversation transcript.

Model call failures:

- Surface the backend error in the transcript through the existing chat error
  path.
- Keep the selected provider unchanged so the user can retry or switch back.
- Do not log API keys or raw provider error bodies that may include sensitive
  request data.

## Testing

Python tests:

- Config loads OpenRouter settings and validates `CUE_MODEL_PROVIDER`.
- OpenRouter client sends the correct URL, headers, model, and messages.
- OpenRouter client extracts text, model, usage, latency, and metadata.
- Backend `/health` and `/mode` include provider/model.
- `POST /mode` switches provider and rejects OpenRouter when the key is absent.
- A provider switch affects subsequent planner calls.

Swift tests:

- Backend client encodes/decodes mode requests with `model_provider`.
- App state syncs provider from health.
- App state performs optimistic provider switch and reverts on failure.
- Timing model decodes `provider`, `model`, and `provider_timing`.

Verification commands:

- `pixi run test-config`
- `pixi run test-cerebras`
- `pixi run test-api`
- `pixi run test-backend`
- `pixi run test-mac`
- `pixi run lint`

## Non-Goals

- Streaming responses or time-to-first-token in this slice.
- Side-by-side simultaneous benchmark calls.
- Sending API keys to Swift.
- Replacing the existing YOLO mode behavior.
- Changing the Cua execution, safety, policy, or approval model beyond passing
  provider state through the existing backend settings.

## Self-Review

- No placeholders remain.
- The design is scoped to the live committed YOLO `/mode` shape.
- OpenRouter is routed through backend-only credentials.
- Normal chat/workflow calls, not just a benchmark probe, are provider-selectable.
- Verification covers Python config/client/API/backend behavior and Swift
  client/app-state/timing behavior.
