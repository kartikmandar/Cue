from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import shutil
import subprocess
from typing import Any

from cue.actions import ActionType, CueAction, WorkflowCategory
from cue.agent_models import IntentResult, NormalizedInput, WorkflowPlan, WorkflowStep
from cue.config import Settings, load_settings
from cue.policy import ApprovalTier


DEMO_ASSETS_DIR = Path(__file__).resolve().parents[1] / "demo_assets"


@dataclass(frozen=True)
class DemoAsset:
    key: str
    filename: str
    category: WorkflowCategory
    expected_app: str
    title: str
    summary: str
    relevant_sections: list[str]
    fields: list[str]
    next_action: str


_DEMO_ASSETS = {
    "hackathon_pdf": DemoAsset(
        key="hackathon_pdf",
        filename="Gemma 4 Hackathon Instruction Document.pdf",
        category=WorkflowCategory.PDF,
        expected_app="Preview",
        title="Gemma 4 Hackathon Instruction Document",
        summary=(
            "Local hackathon brief with judging tracks, timeline, and submission "
            "requirements."
        ),
        relevant_sections=[
            "judging tracks",
            "demo requirements",
            "submission checklist",
        ],
        fields=[],
        next_action="Review the submission checklist before recording the demo.",
    ),
    "sample_contract": DemoAsset(
        key="sample_contract",
        filename="sample_contract.txt",
        category=WorkflowCategory.PDF,
        expected_app="TextEdit",
        title="Sample Service Agreement",
        summary=(
            "Safe local contract surrogate with dates, renewal notice, and demo "
            "obligations."
        ),
        relevant_sections=[
            "parties",
            "scope of work",
            "renewal notice",
            "demo obligations",
        ],
        fields=[],
        next_action="Flag the renewal notice date for human review.",
    ),
    "local_dashboard": DemoAsset(
        key="local_dashboard",
        filename="local_dashboard.html",
        category=WorkflowCategory.BROWSER,
        expected_app="Safari",
        title="Cue Local Demo Dashboard",
        summary=(
            "Local-only dashboard with a status note field and deterministic "
            "project sections."
        ),
        relevant_sections=[
            "status summary",
            "open tasks",
            "demo-safe form",
        ],
        fields=["demo-status-note"],
        next_action="Fill the local demo status note only after confirmation.",
    ),
}


def demo_asset_path(asset: str) -> Path:
    return DEMO_ASSETS_DIR / _asset(asset).filename


def _summary_text(asset: DemoAsset, source_text: str = "") -> str:
    sections = ", ".join(asset.relevant_sections) or "none"
    fields = ", ".join(asset.fields) if asset.fields else "none"
    highlights = _source_highlights(source_text)
    extracted = f" Highlights: {'; '.join(highlights)}." if highlights else ""
    return (
        f"{asset.summary}{extracted} Relevant sections: {sections}. "
        f"Fields: {fields}. Next: {asset.next_action}"
    )


def _single_line(text: str) -> str:
    return " ".join(text.split())


def _extract_asset_text(path: Path) -> str:
    if path.suffix.casefold() == ".pdf":
        return _extract_pdf_text(path)
    try:
        return path.read_text(encoding="utf-8")
    except OSError:
        return ""


def _extract_pdf_text(path: Path) -> str:
    pdftotext = shutil.which("pdftotext")
    if not pdftotext:
        return ""
    try:
        result = subprocess.run(
            [pdftotext, str(path), "-"],
            check=False,
            capture_output=True,
            text=True,
            timeout=10,
        )
    except (OSError, subprocess.TimeoutExpired):
        return ""
    if result.returncode != 0:
        return ""
    return result.stdout


def _source_highlights(text: str) -> list[str]:
    terms = (
        "maximum length",
        "show cerebras speed",
        "side-by-side",
        "agent collaboration",
        "multimodal intelligence",
        "enterprise impact",
        "production readiness",
        "submission instructions",
    )
    lines: list[str] = []
    seen: set[str] = set()
    for raw_line in text.splitlines():
        line = " ".join(raw_line.split())
        if not line:
            continue
        folded = line.casefold()
        if any(term in folded for term in terms) and folded not in seen:
            lines.append(line)
            seen.add(folded)
        if len(lines) >= 6:
            break
    return lines


def create_document_workflow(
    *,
    title: str = "Cue",
    settings: Settings | None = None,
    apply_heading: bool = False,
    focus_verified: bool = False,
) -> WorkflowPlan:
    settings = settings or load_settings()
    cleaned_title = title.strip() or "Cue"
    formatting_allowed = apply_heading and focus_verified
    risk_reasons: list[str] = ["document editing changes state"]
    policy_reason = "TextEdit document workflow requires user confirmation."
    if apply_heading and not focus_verified:
        risk_reasons.append("formatting blocked because focus cannot be verified")
        policy_reason = (
            "TextEdit is allowed, but formatting is blocked because focus cannot "
            "be verified."
        )

    steps = [
        WorkflowStep(
            step_id="document-open-textedit",
            title="Open TextEdit",
            action=CueAction(
                action_type=ActionType.OPEN_APP,
                payload={"app_name": "TextEdit"},
                reason="Open TextEdit as the safest default document app.",
                expected_app="TextEdit",
                changes_state=True,
            ),
            expected_outcome="TextEdit is active.",
            verification_criteria="The active app is TextEdit.",
        ),
        WorkflowStep(
            step_id="document-verify-focus",
            title="Verify TextEdit Focus",
            action=CueAction(
                action_type=ActionType.VERIFY,
                payload={},
                reason="Verify TextEdit is active before typing or formatting.",
                expected_app="TextEdit",
                expected_focus="editable document body" if focus_verified else None,
                changes_state=False,
            ),
            expected_outcome=(
                "TextEdit is active with editable focus."
                if focus_verified
                else "TextEdit is active; formatting remains blocked until focus is known."
            ),
            verification_criteria="Active app is TextEdit before document editing.",
        ),
    ]

    if formatting_allowed:
        steps.append(
            WorkflowStep(
                step_id="document-enable-heading",
                title="Enable Heading Formatting",
                action=CueAction(
                    action_type=ActionType.HOTKEY,
                    payload={"keys": ["command", "b"]},
                    reason=(
                        "Apply low-risk bold heading formatting only after editable "
                        "focus is verified."
                    ),
                    expected_app="TextEdit",
                    expected_focus="editable document body",
                    changes_state=True,
                ),
                expected_outcome="Heading-style bold formatting is enabled for the title.",
                verification_criteria="TextEdit remains active after the formatting hotkey.",
            )
        )

    steps.extend(
        [
            WorkflowStep(
                step_id="document-type-title",
                title="Type Title And Move Below",
                action=CueAction(
                    action_type=ActionType.TYPE_TEXT,
                    payload={"text": f"{cleaned_title}\n\n"},
                    reason="Type the approved title and two line breaks.",
                    expected_app="TextEdit",
                    expected_focus="editable document body" if focus_verified else None,
                    changes_state=True,
                ),
                expected_outcome=(
                    f"The title {cleaned_title!r} is inserted and the cursor below "
                    "the title is ready for body text."
                ),
                verification_criteria=(
                    f"TextEdit contains the title {cleaned_title!r} and remains active."
                ),
            ),
            WorkflowStep(
                step_id="document-verify-result",
                title="Verify Document Result",
                action=CueAction(
                    action_type=ActionType.VERIFY,
                    payload={},
                    reason="Verify the title is visible before continuing.",
                    expected_app="TextEdit",
                    expected_focus="editable document body" if focus_verified else None,
                    changes_state=False,
                ),
                expected_outcome=(
                    f"TextEdit shows {cleaned_title!r} with the cursor below the title."
                ),
                verification_criteria="The title is visible and TextEdit is still active.",
            ),
        ]
    )

    steps = _cap_steps(steps, settings.max_workflow_steps)
    return _plan(
        request=f"Open TextEdit, add the title {cleaned_title}, and place the cursor below.",
        category=WorkflowCategory.DOCUMENT,
        steps=steps,
        settings=settings,
        narration="Cue prepared a safe TextEdit document workflow.",
        risk_level="low",
        approval_tier=ApprovalTier.CONFIRM_EACH_ACTION,
        confirmation_prompt=(
            "Approve opening TextEdit and typing the title before any desktop action?"
        ),
        expected_outcome=(
            f"TextEdit contains the title {cleaned_title!r} and is ready for body text."
        ),
        risk_reasons=risk_reasons,
        allowed_by_policy=True,
        policy_reason=policy_reason,
        audit_event_summary="TextEdit document recipe previewed.",
        workflow_id="recipe-document-textedit",
        metadata={"max_workflow_steps": settings.max_workflow_steps},
    )


def create_browser_pdf_workflow(
    *,
    asset: str = "hackathon_pdf",
    settings: Settings | None = None,
    fill_demo_fields: bool = False,
    confirmed: bool = False,
) -> WorkflowPlan:
    settings = settings or load_settings()
    demo_asset = _asset(asset)
    path = demo_asset_path(demo_asset.key)
    summary_text = _summary_text(demo_asset, _extract_asset_text(path))
    steps = [
        WorkflowStep(
            step_id=f"{demo_asset.key}-open",
            title=f"Open {demo_asset.title}",
            action=CueAction(
                action_type=ActionType.OPEN_FILE,
                payload={"path": str(path)},
                reason="Open the deterministic local demo asset.",
                expected_app=demo_asset.expected_app,
                expected_window=path.name,
                changes_state=True,
            ),
            expected_outcome=f"{demo_asset.title} is open for observation.",
            verification_criteria="The local asset window is active.",
        ),
        WorkflowStep(
            step_id=f"{demo_asset.key}-observe",
            title="Observe Local Asset",
            action=CueAction(
                action_type=ActionType.VERIFY,
                payload={},
                reason="Observe the local file or page before summarizing it.",
                expected_app=demo_asset.expected_app,
                expected_window=path.name,
                changes_state=False,
            ),
            expected_outcome="Cue has observed the local demo asset.",
            verification_criteria="The active window matches the opened local asset.",
        ),
        WorkflowStep(
            step_id=f"{demo_asset.key}-summarize",
            title="Summarize Relevant Sections",
            action=CueAction(
                action_type=ActionType.NONE,
                payload={
                    "summary": demo_asset.summary,
                    "summary_text": summary_text,
                    "relevant_sections": demo_asset.relevant_sections,
                    "fields": demo_asset.fields,
                    "next_action": demo_asset.next_action,
                },
                reason=(
                    "Summarize the local-safe asset and identify relevant sections "
                    "without changing it."
                ),
                expected_app=demo_asset.expected_app,
                expected_window=path.name,
                changes_state=False,
            ),
            expected_outcome=summary_text,
            verification_criteria="No state-changing action is required for the summary.",
        ),
    ]

    risk_reasons: list[str] = []
    approval_tier = ApprovalTier.CONFIRM_EACH_ACTION
    expected_outcome = "Cue opens and summarizes the local asset."
    confirmation_prompt = "Approve opening and summarizing this local demo asset?"

    if fill_demo_fields and demo_asset.key != "local_dashboard":
        risk_reasons.append("field fill blocked for non-dashboard demo asset")
    elif fill_demo_fields and not confirmed:
        steps.append(
            WorkflowStep(
                step_id="local-dashboard-confirm-fill",
                title="Ask Before Filling Local Demo Field",
                action=CueAction(
                    action_type=ActionType.ASK_CONFIRMATION,
                    payload={
                        "prompt": "Approve filling the local demo status note?",
                        "field": "demo-status-note",
                    },
                    reason="Local demo fields can be filled only after confirmation.",
                    expected_app=demo_asset.expected_app,
                    expected_window=path.name,
                    changes_state=False,
                ),
                expected_outcome="The user is asked before the local field is filled.",
                verification_criteria="No field value changes before confirmation.",
            )
        )
        expected_outcome = (
            "Cue summarizes the dashboard and asks before filling a field."
        )
        confirmation_prompt = (
            "Approve opening the dashboard and reviewing the local field?"
        )
    elif fill_demo_fields and confirmed:
        steps.extend(
            [
                WorkflowStep(
                    step_id="local-dashboard-fill-status",
                    title="Fill Local Demo Status",
                    action=CueAction(
                        action_type=ActionType.SET_VALUE,
                        payload={
                            "element_id": "demo-status-note",
                            "value": "Reviewed for the Cue local demo.",
                            "domain": "localhost",
                        },
                        reason=(
                            "Fill only the local demo status note after confirmation."
                        ),
                        expected_app=demo_asset.expected_app,
                        expected_window=path.name,
                        expected_focus="demo-status-note",
                        changes_state=True,
                    ),
                    expected_outcome="The local demo status note contains the approved text.",
                    verification_criteria="The demo-status-note field has the approved value.",
                ),
                WorkflowStep(
                    step_id="local-dashboard-verify-fill",
                    title="Verify Local Demo Fill",
                    action=CueAction(
                        action_type=ActionType.VERIFY,
                        payload={},
                        reason="Verify the local demo field after filling it.",
                        expected_app=demo_asset.expected_app,
                        expected_window=path.name,
                        expected_focus="demo-status-note",
                        changes_state=False,
                    ),
                    expected_outcome="The local demo field fill is verified.",
                    verification_criteria="The approved status note remains visible.",
                ),
            ]
        )
        expected_outcome = "Cue fills and verifies the confirmed local dashboard field."
        confirmation_prompt = "Approve filling the local dashboard status note?"

    steps = _cap_steps(steps, settings.max_workflow_steps)
    return _plan(
        request=f"Open and summarize {demo_asset.title}.",
        category=demo_asset.category,
        steps=steps,
        settings=settings,
        narration=f"Cue prepared a local-safe {demo_asset.category.value} workflow.",
        risk_level="low",
        approval_tier=approval_tier,
        confirmation_prompt=confirmation_prompt,
        expected_outcome=expected_outcome,
        risk_reasons=risk_reasons,
        allowed_by_policy=True,
        policy_reason="Only deterministic local demo assets are used.",
        audit_event_summary=f"{demo_asset.title} workflow previewed.",
        workflow_id=f"recipe-{demo_asset.key}",
        metadata={
            "asset": demo_asset.key,
            "max_workflow_steps": settings.max_workflow_steps,
        },
    )


def create_terminal_readonly_workflow(
    *,
    project_path: str | Path,
    settings: Settings | None = None,
    prompt: str | None = None,
    command_to_run: str | None = None,
    user_confirmed: bool = False,
    type_prompt: bool = False,
) -> WorkflowPlan:
    settings = settings or load_settings()
    project = Path(project_path)
    prepared_prompt = prompt or (
        "Please inspect this project read-only, summarize the app structure, "
        "and do not edit files or run commands."
    )
    metadata = {
        "project_path": str(project),
        "max_workflow_steps": settings.max_workflow_steps,
    }

    if command_to_run and (not settings.allow_terminal_write or not user_confirmed):
        return _plan(
            request="Run a terminal command.",
            category=WorkflowCategory.TERMINAL,
            steps=[],
            settings=settings,
            narration="Cue blocked the terminal command request.",
            risk_level="blocked",
            approval_tier=ApprovalTier.BLOCKED,
            confirmation_prompt="This terminal command is blocked.",
            expected_outcome="No terminal command is typed or executed.",
            risk_reasons=[
                "terminal write blocked unless CUE_ALLOW_TERMINAL_WRITE=true and user confirms"
            ],
            allowed_by_policy=False,
            policy_reason=(
                "Terminal write actions are disabled by default and require explicit "
                "configuration plus confirmation."
            ),
            audit_event_summary="Blocked terminal command workflow.",
            workflow_id="recipe-terminal-blocked",
            metadata=metadata,
        )

    steps = [
        WorkflowStep(
            step_id="terminal-open",
            title="Open Terminal",
            action=CueAction(
                action_type=ActionType.OPEN_APP,
                payload={"app_name": "Terminal"},
                reason="Open Terminal for a read-only Claude Code handoff.",
                expected_app="Terminal",
                changes_state=True,
            ),
            expected_outcome="Terminal is active.",
            verification_criteria="The active app is Terminal.",
        ),
        WorkflowStep(
            step_id="terminal-verify-context",
            title="Verify Terminal Context",
            action=CueAction(
                action_type=ActionType.VERIFY,
                payload={"project_path": str(project)},
                reason="Verify Terminal is active before preparing any handoff text.",
                expected_app="Terminal",
                changes_state=False,
            ),
            expected_outcome=(
                f"Terminal is active; project context is {project} for explanation only."
            ),
            verification_criteria="Terminal is active and no command has run.",
        ),
    ]

    approval_tier = ApprovalTier.CONFIRM_EACH_ACTION
    risk_reasons = ["terminal/coding workflows need approval"]
    expected_outcome = "Cue opens Terminal and prepares a read-only Claude Code prompt."
    policy_reason = "Terminal workflow is read-only by default."

    if command_to_run:
        approval_tier = ApprovalTier.CONFIRM_SENSITIVE
        risk_reasons.append("terminal write explicitly enabled and confirmed")
        expected_outcome = (
            "Cue types the confirmed command text without pressing return."
        )
        policy_reason = (
            "Terminal write is enabled and confirmed; execution still requires review."
        )
        steps.append(
            WorkflowStep(
                step_id="terminal-type-confirmed-command",
                title="Type Confirmed Command Text",
                action=CueAction(
                    action_type=ActionType.TYPE_TEXT,
                    payload={"text": command_to_run},
                    reason=(
                        "Type the confirmed terminal text only because terminal write "
                        "is enabled and the user confirmed."
                    ),
                    expected_app="Terminal",
                    changes_state=True,
                ),
                expected_outcome="The confirmed command text is present but not executed.",
                verification_criteria="Terminal shows the command text with no Return key press.",
            )
        )
    elif type_prompt:
        approval_tier = ApprovalTier.CONFIRM_SENSITIVE
        risk_reasons.append("terminal handoff prompt requires sensitive confirmation")
        expected_outcome = (
            "Cue types a read-only Claude Code handoff prompt without pressing Return."
        )
        policy_reason = (
            "Terminal handoff text is allowed only as a non-executing prompt with "
            "sensitive confirmation."
        )
        steps.append(
            WorkflowStep(
                step_id="terminal-type-handoff-prompt",
                title="Type Claude Code Handoff Prompt",
                action=CueAction(
                    action_type=ActionType.TYPE_TEXT,
                    payload={
                        "text": _single_line(prepared_prompt),
                        "press_return": False,
                        "terminal_write_kind": "handoff_prompt",
                    },
                    reason=(
                        "Type a Claude Code handoff prompt without pressing Return; "
                        "do not execute a command."
                    ),
                    expected_app="Terminal",
                    changes_state=True,
                ),
                expected_outcome=(
                    "The approved handoff prompt is present in Terminal but not executed."
                ),
                verification_criteria=(
                    "Terminal shows the handoff prompt with no Return key press."
                ),
            )
        )
    else:
        steps.append(
            WorkflowStep(
                step_id="terminal-prepare-prompt",
                title="Prepare Claude Code Prompt",
                action=CueAction(
                    action_type=ActionType.NONE,
                    payload={
                        "project_path": str(project),
                        "prepared_prompt": prepared_prompt,
                    },
                    reason=(
                        "Prepare text for the user to review or paste later; do not "
                        "type into Terminal by default."
                    ),
                    expected_app="Terminal",
                    changes_state=False,
                ),
                expected_outcome="A read-only Claude Code prompt is prepared for review.",
                verification_criteria="No terminal input is typed by the recipe.",
            )
        )

    steps = _cap_steps(steps, settings.max_workflow_steps)
    return _plan(
        request="Open Terminal and prepare a read-only Claude Code prompt.",
        category=WorkflowCategory.CODING,
        steps=steps,
        settings=settings,
        narration="Cue prepared a read-only terminal and Claude Code handoff workflow.",
        risk_level="medium",
        approval_tier=approval_tier,
        confirmation_prompt="Approve opening Terminal for a read-only handoff?",
        expected_outcome=expected_outcome,
        risk_reasons=risk_reasons,
        allowed_by_policy=True,
        policy_reason=policy_reason,
        audit_event_summary="Terminal read-only workflow previewed.",
        workflow_id="recipe-terminal-readonly",
        metadata=metadata,
    )


def _plan(
    *,
    request: str,
    category: WorkflowCategory,
    steps: list[WorkflowStep],
    settings: Settings,
    narration: str,
    risk_level: str,
    approval_tier: ApprovalTier,
    confirmation_prompt: str,
    expected_outcome: str,
    risk_reasons: list[str],
    allowed_by_policy: bool,
    policy_reason: str,
    audit_event_summary: str,
    workflow_id: str,
    metadata: dict[str, Any],
) -> WorkflowPlan:
    normalized = NormalizedInput(
        text=request,
        raw_text=request,
        input_mode="recipe",
        source="domain_workflow",
        metadata=metadata,
    )
    intent = IntentResult(
        normalized_input=normalized,
        intent=category.value,
        workflow_required=bool(steps) or category != WorkflowCategory.ANSWER,
        workflow_category=category,
        risk_level=risk_level,
        reason="Deterministic domain workflow recipe.",
        risk_reasons=risk_reasons,
    )
    return WorkflowPlan(
        intent=intent,
        narration=narration,
        workflow_required=bool(steps) or category != WorkflowCategory.ANSWER,
        workflow_category=category,
        steps=steps,
        risk_level=risk_level,
        approval_tier=approval_tier,
        confirmation_prompt=confirmation_prompt,
        expected_outcome=expected_outcome,
        risk_reasons=risk_reasons,
        requires_reviewer_approval=approval_tier == ApprovalTier.GUARDIAN_REQUIRED,
        redaction_applied=False,
        allowed_by_policy=allowed_by_policy,
        policy_reason=policy_reason,
        audit_event_summary=audit_event_summary,
        workflow_id=workflow_id,
    )


def _asset(asset: str) -> DemoAsset:
    try:
        return _DEMO_ASSETS[asset]
    except KeyError as exc:
        known = ", ".join(sorted(_DEMO_ASSETS))
        raise ValueError(
            f"Unknown demo asset {asset!r}. Expected one of: {known}."
        ) from exc


def _cap_steps(steps: list[WorkflowStep], max_steps: int) -> list[WorkflowStep]:
    return steps[: max(0, max_steps)]
