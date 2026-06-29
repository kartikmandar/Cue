from __future__ import annotations

import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from cue.actions import WorkflowCategory
from cue.agent_models import WorkflowPlan
from cue.config import Settings, load_settings
from cue.context import DesktopObservation
from cue.input_agent import normalize_input
from cue.intent_agent import classify_intent
from cue.model_clients import ModelResult, ProviderModelClient
from cue.planner import WorkflowPlanner
from cue.workflows import create_browser_pdf_workflow, create_terminal_readonly_workflow


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
        recipe = _local_workflow_recipe(
            normalized.text, intent.workflow_category, self.settings
        )
        if recipe is not None:
            self.last_result = None
            return recipe

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


def _local_workflow_recipe(
    text: str,
    category: WorkflowCategory,
    settings: Settings,
) -> WorkflowPlan | None:
    normalized = text.casefold()
    if _is_pdf_summary_request(normalized, category):
        return create_browser_pdf_workflow(
            asset=_pdf_asset_for_request(normalized),
            settings=settings,
        )
    if _is_terminal_handoff_request(normalized, category):
        return create_terminal_readonly_workflow(
            project_path=Path.cwd(),
            settings=settings,
            type_prompt=True,
        )
    if category == WorkflowCategory.TERMINAL and "terminal" in normalized:
        return create_terminal_readonly_workflow(
            project_path=Path.cwd(),
            settings=settings,
        )
    return None


def _is_pdf_summary_request(text: str, category: WorkflowCategory) -> bool:
    if category not in {
        WorkflowCategory.PDF,
        WorkflowCategory.BROWSER,
        WorkflowCategory.ANSWER,
    }:
        return False
    mentions_asset = any(
        term in text
        for term in (
            "pdf",
            "hackathon",
            "brief",
            "dashboard",
            "contract",
            "instruction document",
        )
    )
    asks_for_read = any(
        term in text
        for term in ("open", "summarize", "summary", "read", "show", "review")
    )
    return mentions_asset and asks_for_read


def _pdf_asset_for_request(text: str) -> str:
    if "dashboard" in text:
        return "local_dashboard"
    if "contract" in text or "agreement" in text:
        return "sample_contract"
    return "hackathon_pdf"


def _is_terminal_handoff_request(text: str, category: WorkflowCategory) -> bool:
    if category not in {WorkflowCategory.TERMINAL, WorkflowCategory.CODING}:
        return False
    if "terminal" not in text:
        return False
    return any(
        term in text
        for term in ("write", "type", "prompt", "handoff", "inspect", "claude code")
    )


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
