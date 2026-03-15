from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
import json
from pathlib import Path
from typing import Any

from codenames_llm.game import (
    CardRole,
    Clue,
    ClueEvent,
    CodenamesError,
    CodenamesGame,
    GameCard,
    GamePhase,
    GameStatus,
    GeneratedGame,
    GuessEvent,
    HistoryEvent,
    PassEvent,
    PlayerRole,
    Team,
    generate_game,
    initialize_game,
)

DEFAULT_OPENAI_MODEL = "gpt-5.4"
MAX_CONTROLLER_RETRIES = 2


class ControllerKind(StrEnum):
    HUMAN = "human"
    OPENAI = "openai"


class ReasoningEffort(StrEnum):
    NONE = "none"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    XHIGH = "xhigh"


class ControllerError(CodenamesError):
    """Raised when a configured controller cannot act successfully."""


class ControllerConfigurationError(ControllerError):
    """Raised when a controller is misconfigured."""


class ControllerExecutionError(ControllerError):
    """Raised when a controller returns an invalid action or fails to execute."""


class HumanInputRequiredError(ControllerError):
    """Raised when an AI step/run is requested for a human-controlled role."""


@dataclass(frozen=True, slots=True)
class ControllerConfig:
    kind: ControllerKind
    model: str | None = None
    reasoning_effort: ReasoningEffort | None = None

    @property
    def model_name(self) -> str:
        if self.kind is not ControllerKind.OPENAI:
            msg = "Human controllers do not have a model."
            raise ControllerConfigurationError(msg)
        return self.model or DEFAULT_OPENAI_MODEL

    def to_dict(self) -> dict[str, str | None]:
        return {
            "kind": self.kind.value,
            "model": self.model,
            "reasoning_effort": self.reasoning_effort.value if self.reasoning_effort else None,
        }

    @classmethod
    def from_value(cls, value: str | dict[str, Any] | ControllerConfig) -> ControllerConfig:
        if isinstance(value, ControllerConfig):
            return value
        if isinstance(value, str):
            return cls(kind=ControllerKind(value))
        return cls(
            kind=ControllerKind(value["kind"]),
            model=value.get("model"),
            reasoning_effort=(
                ReasoningEffort(value["reasoning_effort"])
                if value.get("reasoning_effort")
                else None
            ),
        )


@dataclass(frozen=True, slots=True)
class ClueDecision:
    word: str
    number: int


@dataclass(frozen=True, slots=True)
class GuessDecision:
    action: str
    word: str | None = None


@dataclass(frozen=True, slots=True)
class AITraceEntry:
    sequence: int
    role: PlayerRole
    team: Team
    controller: ControllerConfig
    action_type: str
    prompt: str | None
    decision: dict[str, Any] | None
    status: str
    message: str
    attempts: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "sequence": self.sequence,
            "role": self.role.value,
            "team": self.team.value,
            "controller": self.controller.to_dict(),
            "action_type": self.action_type,
            "prompt": self.prompt,
            "decision": self.decision,
            "status": self.status,
            "message": self.message,
            "attempts": self.attempts,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> AITraceEntry:
        return cls(
            sequence=payload["sequence"],
            role=PlayerRole(payload["role"]),
            team=Team(payload["team"]),
            controller=ControllerConfig.from_value(payload["controller"]),
            action_type=payload["action_type"],
            prompt=payload.get("prompt"),
            decision=payload.get("decision"),
            status=payload["status"],
            message=payload["message"],
            attempts=payload["attempts"],
        )


DEFAULT_CONTROLLER_ASSIGNMENTS = {
    PlayerRole.RED_SPYMASTER: ControllerConfig(kind=ControllerKind.HUMAN),
    PlayerRole.RED_OPERATIVE: ControllerConfig(kind=ControllerKind.HUMAN),
    PlayerRole.BLUE_SPYMASTER: ControllerConfig(kind=ControllerKind.HUMAN),
    PlayerRole.BLUE_OPERATIVE: ControllerConfig(kind=ControllerKind.HUMAN),
}


@dataclass(slots=True)
class CodenamesSession:
    game: CodenamesGame
    controller_assignments: dict[PlayerRole, ControllerConfig]
    seed: int | None = None
    default_save_path: Path | None = None
    ai_trace: list[AITraceEntry] = field(default_factory=list)

    @classmethod
    def new(
        cls,
        *,
        starting_team: Team,
        seed: int | None = None,
        controller_assignments: dict[PlayerRole, str | dict[str, Any] | ControllerConfig] | None = None,
    ) -> CodenamesSession:
        generated = generate_game(starting_team, seed=seed)
        game = initialize_game(generated)
        assignments = normalize_controller_assignments(controller_assignments)
        return cls(game=game, controller_assignments=assignments, seed=seed)

    @classmethod
    def from_generated_game(
        cls,
        generated_game: GeneratedGame,
        *,
        seed: int | None = None,
        controller_assignments: dict[PlayerRole, str | dict[str, Any] | ControllerConfig] | None = None,
    ) -> CodenamesSession:
        assignments = normalize_controller_assignments(controller_assignments)
        return cls(
            game=initialize_game(generated_game),
            controller_assignments=assignments,
            seed=seed,
        )

    @property
    def active_controller(self) -> ControllerConfig:
        return self.controller_assignments[self.game.active_player]

    @property
    def awaiting_human_input(self) -> bool:
        return self.active_controller.kind is ControllerKind.HUMAN

    @property
    def can_step(self) -> bool:
        return self.game.status is GameStatus.ONGOING and not self.awaiting_human_input

    def save(self, path: str | Path | None = None) -> Path:
        target_path = Path(path) if path is not None else self.default_save_path
        if target_path is None:
            msg = "No save path was provided for this session."
            raise ValueError(msg)

        target_path.parent.mkdir(parents=True, exist_ok=True)
        target_path.write_text(json.dumps(self.to_dict(), indent=2), encoding="utf-8")
        self.default_save_path = target_path
        return target_path

    @classmethod
    def load(cls, path: str | Path) -> CodenamesSession:
        source_path = Path(path)
        payload = json.loads(source_path.read_text(encoding="utf-8"))
        session = cls.from_dict(payload)
        session.default_save_path = source_path
        return session

    def submit_clue(self, word: str, number: int) -> ClueEvent:
        self._ensure_human_turn()
        return self.game.give_clue(self.game.active_player, word, number)

    def submit_guess(self, guessed_word: str) -> GuessEvent:
        self._ensure_human_turn()
        return self.game.guess(self.game.active_player, guessed_word)

    def submit_pass(self) -> PassEvent:
        self._ensure_human_turn()
        return self.game.pass_turn(self.game.active_player)

    def step_active_role(self) -> AITraceEntry:
        if self.game.status is GameStatus.GAME_OVER:
            msg = "Cannot step a controller after the game is over."
            raise ControllerExecutionError(msg)
        if self.awaiting_human_input:
            msg = f"Active role {self.game.active_player.value} is waiting for human input."
            raise HumanInputRequiredError(msg)

        controller = self.active_controller
        attempts = 0
        last_error: Exception | None = None
        for attempts in range(1, MAX_CONTROLLER_RETRIES + 1):
            try:
                acting_role = self.game.active_player
                if self.game.phase is GamePhase.CLUE:
                    decision, prompt = self._run_clue_controller(controller, attempts)
                    message = f"{acting_role.value} gave clue {decision.word} {decision.number}."
                    trace = self._append_trace(
                        action_type="clue",
                        controller=controller,
                        prompt=prompt,
                        decision={"word": decision.word, "number": decision.number},
                        status="succeeded",
                        message=message,
                        attempts=attempts,
                    )
                    return trace

                decision, prompt = self._run_guess_controller(controller, attempts)
                if decision.action == "pass":
                    self.game.pass_turn(acting_role)
                    message = f"{acting_role.value} passed."
                    return self._append_trace(
                        action_type="pass",
                        controller=controller,
                        prompt=prompt,
                        decision={"action": "pass"},
                        status="succeeded",
                        message=message,
                        attempts=attempts,
                    )

                if not decision.word:
                    msg = "The operative chose 'guess' without providing a word."
                    raise ControllerExecutionError(msg)
                event = self.game.guess(self.game.active_player, decision.word)
                message = (
                    f"{event.player.value} guessed {event.guessed_word} "
                    f"({event.revealed_role.value})."
                )
                return self._append_trace(
                    action_type="guess",
                    controller=controller,
                    prompt=prompt,
                    decision={"action": "guess", "word": decision.word},
                    status="succeeded",
                    message=message,
                    attempts=attempts,
                )
            except (CodenamesError, ControllerError) as error:
                last_error = error

        assert last_error is not None
        trace = self._append_trace(
            action_type=self.game.phase.value,
            controller=controller,
            prompt=None,
            decision=None,
            status="failed",
            message=str(last_error),
            attempts=attempts,
        )
        raise ControllerExecutionError(trace.message) from last_error

    def run_until_human_or_game_over(self, *, max_steps: int = 20) -> int:
        if self.awaiting_human_input:
            msg = f"Active role {self.game.active_player.value} is waiting for human input."
            raise HumanInputRequiredError(msg)

        steps = 0
        while self.can_step and steps < max_steps:
            trace = self.step_active_role()
            steps += 1
            if trace.status != "succeeded":
                msg = trace.message
                raise ControllerExecutionError(msg)
        return steps

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": 2,
            "seed": self.seed,
            "default_save_path": str(self.default_save_path) if self.default_save_path else None,
            "controller_assignments": {
                role.value: controller.to_dict()
                for role, controller in self.controller_assignments.items()
            },
            "ai_trace": [entry.to_dict() for entry in self.ai_trace],
            "game": serialize_game(self.game),
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> CodenamesSession:
        controller_assignments = normalize_controller_assignments(
            {
                PlayerRole(role): controller
                for role, controller in payload["controller_assignments"].items()
            }
        )
        default_save_path = payload.get("default_save_path")
        return cls(
            game=deserialize_game(payload["game"]),
            controller_assignments=controller_assignments,
            seed=payload.get("seed"),
            default_save_path=Path(default_save_path) if default_save_path else None,
            ai_trace=[AITraceEntry.from_dict(entry) for entry in payload.get("ai_trace", [])],
        )

    def _ensure_human_turn(self) -> None:
        if not self.awaiting_human_input:
            msg = (
                f"Active role {self.game.active_player.value} is controlled by "
                f"{self.active_controller.kind.value}."
            )
            raise ControllerExecutionError(msg)

    def _run_clue_controller(
        self, controller: ControllerConfig, attempt: int
    ) -> tuple[ClueDecision, str]:
        prompt = build_spymaster_prompt(self, attempt=attempt)
        if controller.kind is not ControllerKind.OPENAI:
            msg = f"Unsupported controller kind {controller.kind.value!r} for clue phase."
            raise ControllerConfigurationError(msg)

        from codenames_llm.controllers.openai_controller import OpenAIController

        decision = OpenAIController().decide_clue(config=controller, prompt=prompt)
        self.game.give_clue(self.game.active_player, decision.word, decision.number)
        return decision, prompt

    def _run_guess_controller(
        self, controller: ControllerConfig, attempt: int
    ) -> tuple[GuessDecision, str]:
        prompt = build_operative_prompt(self, attempt=attempt)
        if controller.kind is not ControllerKind.OPENAI:
            msg = f"Unsupported controller kind {controller.kind.value!r} for guess phase."
            raise ControllerConfigurationError(msg)

        from codenames_llm.controllers.openai_controller import OpenAIController

        return OpenAIController().decide_guess(config=controller, prompt=prompt), prompt

    def _append_trace(
        self,
        *,
        action_type: str,
        controller: ControllerConfig,
        prompt: str | None,
        decision: dict[str, Any] | None,
        status: str,
        message: str,
        attempts: int,
    ) -> AITraceEntry:
        entry = AITraceEntry(
            sequence=len(self.ai_trace) + 1,
            role=self.game.history[-1].player if self.game.history else self.game.active_player,
            team=(self.game.history[-1].team if self.game.history else self.game.active_team),
            controller=controller,
            action_type=action_type,
            prompt=prompt,
            decision=decision,
            status=status,
            message=message,
            attempts=attempts,
        )
        self.ai_trace.append(entry)
        return entry


def normalize_controller_assignments(
    controller_assignments: dict[PlayerRole | str, str | dict[str, Any] | ControllerConfig] | None,
) -> dict[PlayerRole, ControllerConfig]:
    assignments = dict(DEFAULT_CONTROLLER_ASSIGNMENTS)
    for role, controller in (controller_assignments or {}).items():
        normalized_role = role if isinstance(role, PlayerRole) else PlayerRole(role)
        assignments[normalized_role] = ControllerConfig.from_value(controller)
    return assignments


def build_spymaster_prompt(session: CodenamesSession, *, attempt: int) -> str:
    game = session.game
    cards = "\n".join(
        f"- {card.word}: {card.role.value}, revealed={str(card.revealed).lower()}"
        for card in game.cards
    )
    history = format_history(game.history)
    retry_note = "" if attempt == 1 else "Your previous answer was invalid. Try a different legal clue.\n"
    return (
        "You are the active spymaster in a game of Codenames.\n"
        f"Active team: {game.active_team.value}\n"
        f"Round: {game.round_number}\n"
        f"Turn: {game.turn_number}\n"
        f"Remaining agents: red={game.red_agents_remaining}, blue={game.blue_agents_remaining}\n"
        "Board (all roles visible):\n"
        f"{cards}\n"
        f"History:\n{history}\n"
        "Return a clue with a single word and a positive integer number.\n"
        "The clue word must not exactly match a board word, contain a board word, or be contained in a board word.\n"
        f"{retry_note}"
    )


def build_operative_prompt(session: CodenamesSession, *, attempt: int) -> str:
    game = session.game
    visible_cards = "\n".join(
        f"- {card.word}: {'revealed as ' + card.role.value if card.revealed else 'unrevealed'}"
        for card in game.cards
    )
    history = format_history(game.history)
    current_clue = game.current_clue
    retry_note = "" if attempt == 1 else "Your previous answer was invalid. Choose a valid board word or pass.\n"
    return (
        "You are the active operative in a game of Codenames.\n"
        f"Active team: {game.active_team.value}\n"
        f"Round: {game.round_number}\n"
        f"Turn: {game.turn_number}\n"
        f"Current clue: {current_clue.word} {current_clue.number}\n"
        f"Guesses remaining: {game.guesses_remaining}\n"
        "Use only public information. Do not infer from hidden roles.\n"
        "Public board:\n"
        f"{visible_cards}\n"
        f"History:\n{history}\n"
        "Return either action='guess' with a board word, or action='pass'.\n"
        f"{retry_note}"
    )


def format_history(history: list[HistoryEvent]) -> str:
    if not history:
        return "- no prior actions"
    lines: list[str] = []
    for event in history[-8:]:
        if isinstance(event, ClueEvent):
            lines.append(
                f"- {event.player.value} clue {event.clue.word} {event.clue.number}"
            )
        elif isinstance(event, GuessEvent):
            lines.append(
                f"- {event.player.value} guessed {event.guessed_word} ({event.revealed_role.value})"
            )
        else:
            lines.append(f"- {event.player.value} passed")
    return "\n".join(lines)


def serialize_game(game: CodenamesGame) -> dict[str, Any]:
    return {
        "starting_team": game.starting_team.value,
        "active_team": game.active_team.value,
        "active_player": game.active_player.value,
        "round_number": game.round_number,
        "turn_number": game.turn_number,
        "phase": game.phase.value,
        "status": game.status.value,
        "red_agents_remaining": game.red_agents_remaining,
        "blue_agents_remaining": game.blue_agents_remaining,
        "current_clue": (
            {"word": game.current_clue.word, "number": game.current_clue.number}
            if game.current_clue
            else None
        ),
        "guesses_remaining": game.guesses_remaining,
        "winner": game.winner.value if game.winner else None,
        "cards": [
            {"word": card.word, "role": card.role.value, "revealed": card.revealed}
            for card in game.cards
        ],
        "history": [serialize_history_event(event) for event in game.history],
    }


def deserialize_game(payload: dict[str, Any]) -> CodenamesGame:
    return CodenamesGame(
        starting_team=Team(payload["starting_team"]),
        cards=tuple(
            GameCard(
                word=card["word"],
                role=CardRole(card["role"]),
                revealed=card["revealed"],
            )
            for card in payload["cards"]
        ),
        active_team=Team(payload["active_team"]),
        active_player=PlayerRole(payload["active_player"]),
        round_number=payload["round_number"],
        turn_number=payload["turn_number"],
        phase=GamePhase(payload["phase"]),
        status=GameStatus(payload["status"]),
        red_agents_remaining=payload["red_agents_remaining"],
        blue_agents_remaining=payload["blue_agents_remaining"],
        current_clue=deserialize_clue(payload["current_clue"]),
        guesses_remaining=payload["guesses_remaining"],
        winner=Team(payload["winner"]) if payload["winner"] else None,
        history=[deserialize_history_event(event) for event in payload["history"]],
    )


def serialize_history_event(event: HistoryEvent) -> dict[str, Any]:
    if isinstance(event, ClueEvent):
        return {
            "type": "clue",
            "team": event.team.value,
            "player": event.player.value,
            "clue": {"word": event.clue.word, "number": event.clue.number},
            "round_number": event.round_number,
            "turn_number": event.turn_number,
        }
    if isinstance(event, GuessEvent):
        return {
            "type": "guess",
            "team": event.team.value,
            "player": event.player.value,
            "guessed_word": event.guessed_word,
            "revealed_role": event.revealed_role.value,
            "was_correct": event.was_correct,
            "ended_turn": event.ended_turn,
            "ended_game": event.ended_game,
            "round_number": event.round_number,
            "turn_number": event.turn_number,
        }
    return {
        "type": "pass",
        "team": event.team.value,
        "player": event.player.value,
        "round_number": event.round_number,
        "turn_number": event.turn_number,
    }


def deserialize_history_event(payload: dict[str, Any]) -> HistoryEvent:
    if payload["type"] == "clue":
        return ClueEvent(
            team=Team(payload["team"]),
            player=PlayerRole(payload["player"]),
            clue=deserialize_clue(payload["clue"]),
            round_number=payload["round_number"],
            turn_number=payload["turn_number"],
        )
    if payload["type"] == "guess":
        return GuessEvent(
            team=Team(payload["team"]),
            player=PlayerRole(payload["player"]),
            guessed_word=payload["guessed_word"],
            revealed_role=CardRole(payload["revealed_role"]),
            was_correct=payload["was_correct"],
            ended_turn=payload["ended_turn"],
            ended_game=payload["ended_game"],
            round_number=payload["round_number"],
            turn_number=payload["turn_number"],
        )
    return PassEvent(
        team=Team(payload["team"]),
        player=PlayerRole(payload["player"]),
        round_number=payload["round_number"],
        turn_number=payload["turn_number"],
    )


def deserialize_clue(payload: dict[str, Any] | None) -> Clue | None:
    if payload is None:
        return None
    return Clue(word=payload["word"], number=payload["number"])
