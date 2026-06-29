from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from cue.actions import CueAction, WorkflowCategory
from cue.policy import ApprovalTier, PolicyDecision


__all__ = [
    "IntentResult",
    "NarrationResult",
    "NormalizedInput",
    "PlanReview",
    "PolicyDecision",
    "VerificationResult",
    "WorkflowPlan",
    "WorkflowSession",
    "WorkflowStep",
]


class NormalizedInput(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    text: str
    raw_text: str
    input_mode: str = "text"
    source: str = "command_palette"
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("text", "raw_text")
    @classmethod
    def _not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("request text is required")
        return value


class IntentResult(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    normalized_input: NormalizedInput
    intent: str
    workflow_required: bool
    workflow_category: WorkflowCategory
    risk_level: str
    reason: str
    confidence: float = 1.0
    risk_reasons: list[str] = Field(default_factory=list)


class WorkflowStep(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    step_id: str
    title: str
    action: CueAction
    expected_outcome: str
    verification_criteria: str | None = None


class WorkflowPlan(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    intent: IntentResult
    narration: str
    workflow_required: bool
    workflow_category: WorkflowCategory
    steps: list[WorkflowStep] = Field(default_factory=list)
    risk_level: str
    approval_tier: ApprovalTier
    confirmation_prompt: str
    expected_outcome: str
    risk_reasons: list[str] = Field(default_factory=list)
    requires_reviewer_approval: bool
    redaction_applied: bool
    allowed_by_policy: bool
    policy_reason: str
    audit_event_summary: str
    workflow_id: str | None = None


class PlanReview(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    approved: bool
    issues: list[str] = Field(default_factory=list)
    revised_confirmation_prompt: str


class VerificationResult(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    status: Literal["passed", "failed", "unknown"]
    reason: str
    expected: str | None = None
    actual: str | None = None
    next_recommendation: str | None = None


class NarrationResult(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    summary: str
    speakable_text: str
    redaction_applied: bool = False


class WorkflowSession(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    session_id: str
    state: str
    plan: WorkflowPlan | None = None
    current_step_id: str | None = None
    verified_steps: list[str] = Field(default_factory=list)
    last_verification: VerificationResult | None = None
    narration: NarrationResult | None = None
