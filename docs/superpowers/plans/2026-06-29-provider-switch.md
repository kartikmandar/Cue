# Provider Switch Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a runtime Cerebras/OpenRouter provider switch that affects normal Cue chat and workflow planning calls and shows provider timing in the app.

**Architecture:** Add provider-aware settings, a shared model result contract, an OpenRouter client, and a provider router used by `WorkflowPlanner`. Extend existing `/mode` and `/health` payloads, then add a Swift segmented provider picker beside the current YOLO toggle. Wire `create_backend` to a model-backed planner adapter so normal app previews use the selected provider.

**Tech Stack:** Python 3.14, Pixi, FastAPI, Pydantic, httpx, official `cerebras_cloud_sdk`, SwiftUI/AppKit, XCTest, pytest, ruff.

## Global Constraints

- All implementation files live under `Cue/`.
- Use Pixi for every verification command.
- Preserve existing YOLO mode behavior and the `/mode` endpoint pattern.
- Keep API keys backend-only; Swift sends provider names only.
- OpenRouter model default: `google/gemma-4-31b-it:free`.
- Cerebras model default: `gemma-4-31b`.
- Do not overwrite unrelated user changes in `scripts/run_desktop.sh` or `tests/test_run_desktop_script.py`.

---

### Task 1: Provider Settings And Mode API

**Files:**
- Modify: `cue/config.py`
- Modify: `cue/backend.py`
- Modify: `cue/api.py`
- Modify: `.env.example`
- Test: `tests/test_config.py`
- Test: `tests/test_api.py`
- Test: `tests/test_backend.py`

**Interfaces:**
- Produces: `Settings.model_provider`, `Settings.openrouter_api_key`, `Settings.openrouter_model`, `Settings.openrouter_base_url`, `Settings.openrouter_http_referer`, `Settings.openrouter_app_title`.
- Produces: `CueBackend.mode() -> dict[str, str | bool]`.
- Produces: `CueBackend.set_mode(yolo_mode: bool | None = None, model_provider: str | None = None) -> dict[str, str | bool]`.
- Produces: `/health` and `/mode` payloads with `yolo_mode`, `model_provider`, and `model`.

- [ ] **Step 1: Write failing config tests**

Add tests that prove OpenRouter env fields load and invalid providers are rejected.

- [ ] **Step 2: Run config tests and verify failure**

Run: `pixi run test-config`
Expected: FAIL because provider fields do not exist yet.

- [ ] **Step 3: Implement settings fields and env loading**

Add provider fields, defaults, and validation in `cue/config.py`. Keep `CEREBRAS_API_KEY` required for existing startup behavior.

- [ ] **Step 4: Run config tests and verify pass**

Run: `pixi run test-config`
Expected: PASS.

- [ ] **Step 5: Write failing API/backend mode tests**

Add tests for `/health`, `GET /mode`, `POST /mode` with provider switching, and OpenRouter selection without a key.

- [ ] **Step 6: Run API/backend tests and verify failure**

Run: `pixi run test-api tests/test_backend.py -v`
Expected: FAIL because mode payloads do not include provider state yet.

- [ ] **Step 7: Implement mode payload and provider validation**

Extend `ModeRequest`, `CueBackend.mode`, and `CueBackend.set_mode`. Update `.env.example` with OpenRouter keys/settings.

- [ ] **Step 8: Run API/backend tests and verify pass**

Run: `pixi run test-api && pixi run test-backend`
Expected: PASS.

- [ ] **Step 9: Commit Task 1**

Run: `git add cue/config.py cue/backend.py cue/api.py .env.example tests/test_config.py tests/test_api.py tests/test_backend.py && git commit -m "feat: add provider mode settings"`

### Task 2: Provider Clients And Model Router

**Files:**
- Create: `cue/model_clients.py`
- Create: `cue/openrouter_client.py`
- Modify: `cue/cerebras_client.py`
- Modify: `cue/planner.py`
- Test: `tests/test_cerebras_client.py`
- Test: `tests/test_openrouter_client.py`
- Test: `tests/test_planner_schema.py`

**Interfaces:**
- Produces: `ModelResult(text, latency_ms, usage, time_info, provider, model)`.
- Produces: `ProviderModelClient(settings).complete(messages, response_format=None) -> ModelResult`.
- Produces: `OpenRouterClient(settings, http_client=None, clock=time.perf_counter).complete(...) -> ModelResult`.
- Keeps: `CerebrasResult` import compatibility as an alias for `ModelResult`.

- [ ] **Step 1: Write failing model client tests**

Cover OpenRouter request URL, headers, body, response parsing, latency, usage, and metadata extraction.

- [ ] **Step 2: Run client tests and verify failure**

Run: `pixi run test-cerebras tests/test_openrouter_client.py -v`
Expected: FAIL because shared model clients do not exist yet.

- [ ] **Step 3: Implement shared model client contracts**

Create `cue/model_clients.py`, update `cue/cerebras_client.py` to return provider/model metadata, and add `cue/openrouter_client.py`.

- [ ] **Step 4: Run client tests and verify pass**

Run: `pixi run test-cerebras tests/test_openrouter_client.py -v`
Expected: PASS.

- [ ] **Step 5: Write failing planner router test**

Add a test proving `WorkflowPlanner` can use `ProviderModelClient` and preserves provider result metadata for later timing capture.

- [ ] **Step 6: Run planner tests and verify failure**

Run: `pixi run test-planner`
Expected: FAIL until planner stores last result metadata.

- [ ] **Step 7: Implement planner result capture**

Store the last `ModelResult` on `WorkflowPlanner` as `last_result` without changing the plan schema.

- [ ] **Step 8: Run planner tests and verify pass**

Run: `pixi run test-planner`
Expected: PASS.

- [ ] **Step 9: Commit Task 2**

Run: `git add cue/model_clients.py cue/openrouter_client.py cue/cerebras_client.py cue/planner.py tests/test_cerebras_client.py tests/test_openrouter_client.py tests/test_planner_schema.py && git commit -m "feat: add provider model clients"`

### Task 3: Model-Backed Backend Planner And Timing

**Files:**
- Create: `cue/model_planner.py`
- Modify: `cue/backend.py`
- Modify: `tests/test_backend.py`
- Modify: `tests/test_api.py`

**Interfaces:**
- Produces: `ModelBackedPlanner(settings). __call__(request, observation) -> WorkflowPlan`.
- Produces: backend timing payload fields `provider`, `model`, `latency_ms`, `token_usage`, `provider_timing`.

- [ ] **Step 1: Write failing backend timing tests**

Add tests proving the backend includes provider/model timing from the planner result and provider switch affects the next planner call.

- [ ] **Step 2: Run backend/API tests and verify failure**

Run: `pixi run test-backend tests/test_api.py -v`
Expected: FAIL because timing does not include model fields and provider switch is not routed into planner calls.

- [ ] **Step 3: Implement model-backed planner adapter**

Create `cue/model_planner.py` to build observation context from `DesktopObservation.to_prompt_context`, classify intent, and call `WorkflowPlanner`.

- [ ] **Step 4: Wire create_backend to model-backed planner**

Update `create_backend` to use `ModelBackedPlanner(settings=loaded_settings)`. Keep tests that inject planners unaffected.

- [ ] **Step 5: Add timing metadata to backend response**

Read `last_result` from the active planner and merge provider/model/latency/tokens/provider timing into `timing`.

- [ ] **Step 6: Run backend/API tests and verify pass**

Run: `pixi run test-backend && pixi run test-api`
Expected: PASS.

- [ ] **Step 7: Commit Task 3**

Run: `git add cue/model_planner.py cue/backend.py tests/test_backend.py tests/test_api.py && git commit -m "feat: route backend through selected model provider"`

### Task 4: Swift Provider Switch And Timing UI

**Files:**
- Modify: `apps/mac/CueApp/Models.swift`
- Modify: `apps/mac/CueApp/BackendClient.swift`
- Modify: `apps/mac/CueApp/AppState.swift`
- Modify: `apps/mac/CueApp/ConversationView.swift`
- Modify: `apps/mac/CueApp/TimingView.swift`
- Modify: `apps/mac/CueAppTests/BackendClientTests.swift`
- Modify: `apps/mac/CueAppTests/AppStateConversationTests.swift`

**Interfaces:**
- Produces: `CueModelProvider` enum with `cerebras` and `openrouter`.
- Produces: `AppState.modelProvider`.
- Produces: `BackendClient.setMode(yoloMode:modelProvider:)`.
- Extends: `CueTiming.provider` and `CueTiming.providerTiming`.

- [ ] **Step 1: Write failing Swift client/model tests**

Add tests for decoding health/mode provider fields, encoding `model_provider`, and decoding timing provider fields.

- [ ] **Step 2: Run Swift tests and verify failure**

Run: `pixi run test-mac`
Expected: FAIL because Swift models do not include provider fields yet.

- [ ] **Step 3: Implement Swift models and backend client mode request**

Extend existing models and replace `setYoloMode` transport with a mode request that can include provider.

- [ ] **Step 4: Run Swift tests and verify pass for client/model tests**

Run: `pixi run test-mac`
Expected: PASS or expose AppState/UI gaps for the next step.

- [ ] **Step 5: Write failing AppState provider switch tests**

Add tests for health sync, optimistic provider switching, and revert-on-failure.

- [ ] **Step 6: Implement AppState and UI picker**

Add segmented provider picker beside Speech/YOLO. Update `TimingView` to show provider and model.

- [ ] **Step 7: Run Swift tests and verify pass**

Run: `pixi run test-mac`
Expected: PASS.

- [ ] **Step 8: Commit Task 4**

Run: `git add apps/mac/CueApp/Models.swift apps/mac/CueApp/BackendClient.swift apps/mac/CueApp/AppState.swift apps/mac/CueApp/ConversationView.swift apps/mac/CueApp/TimingView.swift apps/mac/CueAppTests/BackendClientTests.swift apps/mac/CueAppTests/AppStateConversationTests.swift && git commit -m "feat: add app provider switch"`

### Task 5: Docs And Full Verification

**Files:**
- Modify: `README.md`

**Interfaces:**
- Documents provider env vars, app switch behavior, and timing comparison workflow.

- [ ] **Step 1: Update README**

Document `OPENROUTER_API_KEY`, `OPENROUTER_MODEL=google/gemma-4-31b-it:free`, `CUE_MODEL_PROVIDER`, and the app provider switch.

- [ ] **Step 2: Run targeted verification**

Run: `pixi run test-config && pixi run test-cerebras && pixi run test-api && pixi run test-backend && pixi run test-mac && pixi run lint`
Expected: all commands pass.

- [ ] **Step 3: Check worktree and commit docs**

Run: `git status --short`
Expected: only intentional README/provider files remain unstaged. Do not stage unrelated user changes in `scripts/run_desktop.sh` or `tests/test_run_desktop_script.py`.

- [ ] **Step 4: Commit README if changed**

Run: `git add README.md && git commit -m "docs: document provider switching"`

- [ ] **Step 5: Final status**

Run: `git status --short`
Expected: no uncommitted provider-switch changes; unrelated user edits may remain.
