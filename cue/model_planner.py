from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Any

from cue.agent_models import WorkflowPlan
from cue.config import Settings, load_settings
from cue.context import DesktopObservation
from cue.input_agent import normalize_input
from cue.intent_agent import classify_intent
from cue.model_clients import ModelResult, ProviderModelClient
from cue.planner import WorkflowPlanner


class ModelBackedPlanner:
    def __init__(
        self,
        *,
        settings: Settings | None = None,
        workflow_planner: Any | None = None,
    ) -> None:
        self.settings = settings or load_settings()
        self._workflow_planner = workflow_planner or WorkflowPlanner(
            settings=self.settings,
            client=ProviderModelClient(settings_getter=lambda: self.settings),
        )
        self.last_result: ModelResult | None = None
        self._sync_workflow_planner_settings()

    def __call__(
        self,
        request: str,
        observation: DesktopObservation | Mapping[str, Any],
    ) -> WorkflowPlan:
        self._sync_workflow_planner_settings()
        normalized = normalize_input(request, source="backend")
        intent = classify_intent(normalized)
        plan = self._workflow_planner.create_plan(
            normalized_input=normalized,
            intent=intent,
            observation_context=_observation_context(
                observation,
                include_screenshot=self.settings.save_screenshots,
            ),
            state_graph_summary="No pending workflow.",
            policy_summary=_policy_summary(self.settings),
        )
        self.last_result = getattr(self._workflow_planner, "last_result", None)
        return plan

    def _sync_workflow_planner_settings(self) -> None:
        if hasattr(self._workflow_planner, "settings"):
            self._workflow_planner.settings = self.settings


def _observation_context(
    observation: DesktopObservation | Mapping[str, Any],
    *,
    include_screenshot: bool,
) -> str:
    if isinstance(observation, DesktopObservation):
        return observation.to_prompt_context(include_screenshot=include_screenshot)
    return json.dumps(dict(observation), sort_keys=True, default=str)


def _policy_summary(settings: Settings) -> str:
    terminal_write = "enabled" if settings.allow_terminal_write else "blocked"
    return "\n".join(
        [
            f"Allowed apps: {', '.join(settings.allowed_apps)}",
            f"Blocked apps: {', '.join(settings.blocked_apps)}",
            f"Allowed domains: {', '.join(settings.allowed_domains)}",
            f"YOLO mode: {'enabled' if settings.yolo_mode else 'disabled'}",
            f"Terminal write: {terminal_write}",
            f"Approval tier: {settings.approval_tier}",
        ]
    )
