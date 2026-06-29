from pathlib import Path

from cue.actions import ActionType, WorkflowCategory
from cue.config import Settings
from cue.policy import ApprovalTier
from cue.workflows import (
    create_browser_pdf_workflow,
    create_document_workflow,
    create_terminal_readonly_workflow,
    demo_asset_path,
)


def make_settings(**overrides):
    values = {
        "cerebras_api_key": "test-key",
        "allowed_apps": [
            "TextEdit",
            "Preview",
            "Safari",
            "Google Chrome",
            "Terminal",
            "Finder",
        ],
        "allowed_domains": ["localhost", "127.0.0.1"],
        "max_workflow_steps": 5,
    }
    values.update(overrides)
    return Settings(**values)


def action_types(plan):
    return [step.action.action_type for step in plan.steps]


def test_document_recipe_opens_textedit_types_title_and_places_cursor_below():
    plan = create_document_workflow(
        title="Cue",
        settings=make_settings(),
        apply_heading=True,
        focus_verified=True,
    )

    assert plan.workflow_category == WorkflowCategory.DOCUMENT
    assert plan.approval_tier == ApprovalTier.CONFIRM_EACH_ACTION
    assert action_types(plan) == [
        ActionType.OPEN_APP,
        ActionType.VERIFY,
        ActionType.HOTKEY,
        ActionType.TYPE_TEXT,
        ActionType.VERIFY,
    ]
    assert plan.steps[0].action.payload == {"app_name": "TextEdit"}
    assert plan.steps[3].action.payload["text"] == "Cue\n\n"
    assert "cursor below" in plan.steps[3].expected_outcome.casefold()
    assert len(plan.steps) <= plan.intent.normalized_input.metadata["max_workflow_steps"]


def test_document_recipe_blocks_formatting_when_focus_is_not_verified():
    plan = create_document_workflow(
        title="Cue",
        settings=make_settings(),
        apply_heading=True,
        focus_verified=False,
    )

    assert ActionType.HOTKEY not in action_types(plan)
    assert any("formatting blocked" in reason for reason in plan.risk_reasons)
    assert "focus cannot be verified" in plan.policy_reason.casefold()


def test_browser_pdf_recipe_supports_local_assets_and_requires_confirmation_to_fill():
    for asset_name in ("hackathon_pdf", "sample_contract", "local_dashboard"):
        assert demo_asset_path(asset_name).exists()

    contract_plan = create_browser_pdf_workflow(
        asset="sample_contract",
        settings=make_settings(),
    )
    assert contract_plan.workflow_category == WorkflowCategory.PDF
    assert contract_plan.steps[0].action.payload["path"].endswith("sample_contract.txt")
    assert "renewal notice" in _summary_payload(contract_plan)["relevant_sections"]

    dashboard_preview = create_browser_pdf_workflow(
        asset="local_dashboard",
        settings=make_settings(),
        fill_demo_fields=True,
        confirmed=False,
    )
    assert ActionType.ASK_CONFIRMATION in action_types(dashboard_preview)
    assert ActionType.SET_VALUE not in action_types(dashboard_preview)

    dashboard_confirmed = create_browser_pdf_workflow(
        asset="local_dashboard",
        settings=make_settings(),
        fill_demo_fields=True,
        confirmed=True,
    )
    assert ActionType.SET_VALUE in action_types(dashboard_confirmed)
    fill_step = next(
        step
        for step in dashboard_confirmed.steps
        if step.action.action_type == ActionType.SET_VALUE
    )
    assert fill_step.action.payload == {
        "element_id": "demo-status-note",
        "value": "Reviewed for the Cue local demo.",
        "domain": "localhost",
    }


def test_terminal_recipe_is_read_only_by_default_and_blocks_command_execution():
    settings = make_settings(allow_terminal_write=False)
    plan = create_terminal_readonly_workflow(
        project_path=Path("/tmp/cue-demo-project"),
        settings=settings,
    )

    assert plan.workflow_category == WorkflowCategory.CODING
    assert action_types(plan) == [
        ActionType.OPEN_APP,
        ActionType.VERIFY,
        ActionType.NONE,
    ]
    prepared_prompt = plan.steps[2].action.payload["prepared_prompt"]
    assert "inspect this project read-only" in prepared_prompt.casefold()
    assert all(not step.action.changes_state for step in plan.steps[1:])

    blocked = create_terminal_readonly_workflow(
        project_path=Path("/tmp/cue-demo-project"),
        settings=settings,
        command_to_run="rm -rf .",
        user_confirmed=False,
    )
    assert blocked.allowed_by_policy is False
    assert blocked.approval_tier == ApprovalTier.BLOCKED
    assert blocked.steps == []
    assert any("terminal write blocked" in reason for reason in blocked.risk_reasons)


def test_workflow_recipes_stay_under_configured_step_limit():
    settings = make_settings(max_workflow_steps=3)
    plans = [
        create_document_workflow(
            title="Cue",
            settings=settings,
            apply_heading=True,
            focus_verified=True,
        ),
        create_browser_pdf_workflow(
            asset="local_dashboard",
            settings=settings,
            fill_demo_fields=True,
            confirmed=True,
        ),
        create_terminal_readonly_workflow(
            project_path=Path("/tmp/cue-demo-project"),
            settings=settings,
        ),
    ]

    for plan in plans:
        assert len(plan.steps) <= settings.max_workflow_steps


def _summary_payload(plan):
    return next(
        step.action.payload
        for step in plan.steps
        if step.action.action_type == ActionType.NONE
        and "relevant_sections" in step.action.payload
    )
