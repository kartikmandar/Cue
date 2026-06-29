from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class ActionType(str, Enum):
    NONE = "none"
    OPEN_APP = "open_app"
    OPEN_FILE = "open_file"
    ACTIVATE_APP = "activate_app"
    CLICK = "click"
    TYPE_TEXT = "type_text"
    HOTKEY = "hotkey"
    PRESS_KEY = "press_key"
    SCROLL = "scroll"
    SET_VALUE = "set_value"
    FOCUS_ELEMENT = "focus_element"
    WAIT_FOR_WINDOW = "wait_for_window"
    ASK_CONFIRMATION = "ask_confirmation"
    REQUEST_REVIEWER_APPROVAL = "request_reviewer_approval"
    VERIFY = "verify"
    CANCEL_WORKFLOW = "cancel_workflow"


class WorkflowCategory(str, Enum):
    ANSWER = "answer"
    DESKTOP = "desktop"
    APP_LAUNCH = "app_launch"
    DOCUMENT = "document"
    BROWSER = "browser"
    PDF = "pdf"
    TERMINAL = "terminal"
    CODING = "coding"
    SENSITIVE = "sensitive"
    NONE = "none"


class CueAction(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    action_type: ActionType = ActionType.NONE
    payload: dict[str, Any] = Field(default_factory=dict)
    reason: str
    expected_app: str | None = None
    expected_window: str | None = None
    expected_focus: str | None = None
    changes_state: bool = False
