from __future__ import annotations

import json
from typing import Any

from pydantic import ValidationError

from cue.agent_models import IntentResult, NormalizedInput, WorkflowPlan
from cue.cerebras_client import CerebrasClient
from cue.config import Settings, load_settings
from cue.input_agent import normalize_input
from cue.intent_agent import classify_intent


class WorkflowPlanner:
    def __init__(
        self,
        *,
        client: Any | None = None,
        settings: Settings | None = None,
    ) -> None:
        self.settings = settings or load_settings()
        self.client = client or CerebrasClient(settings=self.settings)

    def create_plan(
        self,
        *,
        normalized_input: str | NormalizedInput,
        intent: IntentResult | None = None,
        observation_context: str,
        state_graph_summary: str,
        policy_summary: str,
    ) -> WorkflowPlan:
        normalized = normalize_input(normalized_input)
        classified_intent = intent or classify_intent(normalized)
        response_format = workflow_plan_response_format()
        result = self.client.complete(
            _planner_messages(
                normalized,
                classified_intent,
                observation_context=observation_context,
                state_graph_summary=state_graph_summary,
                policy_summary=policy_summary,
            ),
            response_format=response_format,
        )
        plan = _parse_plan(result.text)
        return _cap_steps(plan, self.settings.max_workflow_steps)


def workflow_plan_response_format() -> dict[str, Any]:
    return {
        "type": "json_schema",
        "json_schema": {
            "name": "cue_workflow_plan",
            "schema": WorkflowPlan.model_json_schema(),
        },
    }


def _planner_messages(
    normalized_input: NormalizedInput,
    intent: IntentResult,
    *,
    observation_context: str,
    state_graph_summary: str,
    policy_summary: str,
) -> list[dict[str, str]]:
    schema = json.dumps(WorkflowPlan.model_json_schema(), sort_keys=True)
    return [
        {
            "role": "system",
            "content": (
                "You are Cue's Planner Agent. Return only schema-valid JSON. "
                "Prefer app launch -> verify -> action -> verify patterns. "
                "Use typed Cue actions only."
            ),
        },
        {
            "role": "user",
            "content": "\n\n".join(
                [
                    f"Request: {normalized_input.text}",
                    f"Intent: {intent.model_dump(mode='json')}",
                    f"Observation context:\n{observation_context}",
                    f"State graph summary:\n{state_graph_summary}",
                    f"Policy summary:\n{policy_summary}",
                    f"WorkflowPlan JSON schema:\n{schema}",
                ]
            ),
        },
    ]


def _parse_plan(text: str) -> WorkflowPlan:
    try:
        payload = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ValueError("Planner returned invalid JSON.") from exc

    try:
        return WorkflowPlan.model_validate(payload)
    except ValidationError as exc:
        raise ValueError("Planner returned JSON that does not match WorkflowPlan.") from exc


def _cap_steps(plan: WorkflowPlan, max_steps: int) -> WorkflowPlan:
    if max_steps < 0:
        max_steps = 0
    if len(plan.steps) <= max_steps:
        return plan
    return plan.model_copy(update={"steps": plan.steps[:max_steps]})
