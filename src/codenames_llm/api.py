from __future__ import annotations

from dataclasses import dataclass, field
from uuid import uuid4

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, ConfigDict, Field

from codenames_llm.game import CodenamesError, InvalidActionError, PlayerRole, Team
from codenames_llm.session import (
    CodenamesSession,
    ControllerConfigurationError,
    ControllerError,
    ControllerExecutionError,
    ControllerKind,
    HumanInputRequiredError,
    ReasoningEffort,
)
from codenames_llm.views import build_session_view


class ControllerConfigRequest(BaseModel):
    kind: ControllerKind
    model: str | None = None
    reasoning_effort: ReasoningEffort | None = None

    model_config = ConfigDict(use_enum_values=False)


class CreateSessionRequest(BaseModel):
    starts: Team
    seed: int | None = None
    controllers: dict[PlayerRole, ControllerConfigRequest] | None = None

    model_config = ConfigDict(use_enum_values=False)


class ClueRequest(BaseModel):
    word: str
    number: int


class GuessRequest(BaseModel):
    word: str = Field(min_length=1)


class RunRequest(BaseModel):
    max_steps: int = Field(default=20, ge=1, le=100)


@dataclass(slots=True)
class SessionStore:
    sessions: dict[str, CodenamesSession] = field(default_factory=dict)

    def create(self, request: CreateSessionRequest) -> tuple[str, CodenamesSession]:
        assignments = {
            role: config.model_dump(mode="python")
            for role, config in (request.controllers or {}).items()
        }
        session = CodenamesSession.new(
            starting_team=request.starts,
            seed=request.seed,
            controller_assignments=assignments,
        )
        session_id = uuid4().hex
        self.sessions[session_id] = session
        return session_id, session

    def get(self, session_id: str) -> CodenamesSession:
        session = self.sessions.get(session_id)
        if session is None:
            msg = f"Session {session_id!r} was not found."
            raise KeyError(msg)
        return session


def create_app() -> FastAPI:
    app = FastAPI(title="Codenames LLM API")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    store = SessionStore()
    app.state.session_store = store

    @app.get("/api/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.post("/api/sessions")
    def create_session(request: CreateSessionRequest) -> dict[str, object]:
        session_id, session = store.create(request)
        return build_session_view(session_id, session)

    @app.get("/api/sessions/{session_id}")
    def get_session(session_id: str) -> dict[str, object]:
        session = _get_session_or_404(store, session_id)
        return build_session_view(session_id, session)

    @app.post("/api/sessions/{session_id}/clue")
    def submit_clue(session_id: str, request: ClueRequest) -> dict[str, object]:
        session = _get_session_or_404(store, session_id)
        try:
            session.submit_clue(request.word, request.number)
        except (CodenamesError, ControllerError) as error:
            raise _to_http_error(error) from error
        return build_session_view(session_id, session)

    @app.post("/api/sessions/{session_id}/guess")
    def submit_guess(session_id: str, request: GuessRequest) -> dict[str, object]:
        session = _get_session_or_404(store, session_id)
        try:
            session.submit_guess(request.word)
        except (CodenamesError, ControllerError) as error:
            raise _to_http_error(error) from error
        return build_session_view(session_id, session)

    @app.post("/api/sessions/{session_id}/pass")
    def submit_pass(session_id: str) -> dict[str, object]:
        session = _get_session_or_404(store, session_id)
        try:
            session.submit_pass()
        except (CodenamesError, ControllerError) as error:
            raise _to_http_error(error) from error
        return build_session_view(session_id, session)

    @app.post("/api/sessions/{session_id}/step")
    def step_session(session_id: str) -> dict[str, object]:
        session = _get_session_or_404(store, session_id)
        try:
            session.step_active_role()
        except (CodenamesError, ControllerError) as error:
            raise _to_http_error(error) from error
        return build_session_view(session_id, session)

    @app.post("/api/sessions/{session_id}/run")
    def run_session(session_id: str, request: RunRequest) -> dict[str, object]:
        session = _get_session_or_404(store, session_id)
        try:
            session.run_until_human_or_game_over(max_steps=request.max_steps)
        except (CodenamesError, ControllerError) as error:
            raise _to_http_error(error) from error
        return build_session_view(session_id, session)

    return app


def _get_session_or_404(store: SessionStore, session_id: str) -> CodenamesSession:
    try:
        return store.get(session_id)
    except KeyError as error:
        raise HTTPException(
            status_code=404,
            detail={"error": "session_not_found", "message": str(error)},
        ) from error


def _to_http_error(error: Exception) -> HTTPException:
    if isinstance(error, HumanInputRequiredError):
        error_code = "human_input_required"
    elif isinstance(error, ControllerConfigurationError):
        error_code = "controller_unavailable"
    elif isinstance(error, ControllerExecutionError):
        error_code = "controller_execution_failed"
    elif isinstance(error, InvalidActionError):
        error_code = "invalid_action"
    else:
        error_code = "invalid_request"

    return HTTPException(
        status_code=400,
        detail={"error": error_code, "message": str(error)},
    )


app = create_app()
