from __future__ import annotations

from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel, ConfigDict

from cue.backend import CueBackend, SessionNotFound, create_backend


class PreviewRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    request: str | None = None
    text: str | None = None


class SessionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    session_id: str


class ChatRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    request: str | None = None
    text: str | None = None
    conversation_id: str | None = None


class ApproveRequest(SessionRequest):
    actor: str = "user"


class ReviewRequest(SessionRequest):
    actor: str = "guardian"


class ConfirmReviewerRequest(SessionRequest):
    approved: bool
    actor: str = "guardian"
    reason: str | None = None


class CancelRequest(SessionRequest):
    reason: str = "Workflow cancelled."


class ModeRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    yolo_mode: bool


def create_app(backend: CueBackend | None = None) -> FastAPI:
    cue_backend = backend or create_backend()
    app = FastAPI(title="Cue Local Backend", version="0.1.0")
    app.state.backend = cue_backend

    @app.get("/health")
    def health() -> dict[str, str | bool]:
        return {
            "status": "ok",
            "app": "cue",
            "yolo_mode": cue_backend.settings.yolo_mode,
        }

    @app.get("/mode")
    def mode() -> dict[str, bool]:
        return cue_backend.mode()

    @app.post("/mode")
    def set_mode(request: ModeRequest) -> dict[str, bool]:
        return cue_backend.set_yolo_mode(request.yolo_mode)

    @app.post("/session/preview")
    def preview(request: PreviewRequest) -> dict:
        text = (request.request or request.text or "").strip()
        if not text:
            raise HTTPException(status_code=400, detail="request text is required")
        return cue_backend.preview(text)

    @app.post("/chat")
    def chat(request: ChatRequest) -> dict:
        text = (request.request or request.text or "").strip()
        if not text:
            raise HTTPException(status_code=400, detail="request text is required")
        return cue_backend.chat(text, conversation_id=request.conversation_id)

    @app.post("/session/approve")
    def approve(request: ApproveRequest) -> dict:
        return _or_404(
            lambda: cue_backend.approve(request.session_id, actor=request.actor)
        )

    @app.post("/session/next")
    def next_step(request: SessionRequest) -> dict:
        return _or_404(lambda: cue_backend.next(request.session_id))

    @app.post("/session/request-review")
    def request_review(request: ReviewRequest) -> dict:
        return _or_404(lambda: cue_backend.request_review(request.session_id))

    @app.post("/session/confirm-reviewer")
    def confirm_reviewer(request: ConfirmReviewerRequest) -> dict:
        return _or_404(
            lambda: cue_backend.confirm_reviewer(
                request.session_id,
                approved=request.approved,
                actor=request.actor,
                reason=request.reason,
            )
        )

    @app.post("/session/cancel")
    def cancel(request: CancelRequest) -> dict:
        return _or_404(
            lambda: cue_backend.cancel(request.session_id, reason=request.reason)
        )

    @app.get("/session/{session_id}")
    def get_session(session_id: str) -> dict:
        return _or_404(lambda: cue_backend.get_session(session_id))

    @app.get("/audit/events")
    def audit_events(
        session_id: str | None = Query(default=None),
    ) -> dict[str, list[dict]]:
        return _or_404(lambda: {"events": cue_backend.audit_events(session_id)})

    return app


def _or_404(callback):
    try:
        return callback()
    except SessionNotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
