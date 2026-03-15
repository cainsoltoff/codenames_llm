from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any

from codenames_llm.game import (
    CardRole,
    Clue,
    ClueEvent,
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


class ControllerKind(str):
    HUMAN = "human"


DEFAULT_CONTROLLER_ASSIGNMENTS = {
    PlayerRole.RED_SPYMASTER: ControllerKind.HUMAN,
    PlayerRole.RED_OPERATIVE: ControllerKind.HUMAN,
    PlayerRole.BLUE_SPYMASTER: ControllerKind.HUMAN,
    PlayerRole.BLUE_OPERATIVE: ControllerKind.HUMAN,
}


@dataclass(slots=True)
class CodenamesSession:
    game: CodenamesGame
    controller_assignments: dict[PlayerRole, str]
    seed: int | None = None
    default_save_path: Path | None = None

    @classmethod
    def new(
        cls,
        *,
        starting_team: Team,
        seed: int | None = None,
        controller_assignments: dict[PlayerRole, str] | None = None,
    ) -> CodenamesSession:
        generated = generate_game(starting_team, seed=seed)
        game = initialize_game(generated)
        assignments = dict(controller_assignments or DEFAULT_CONTROLLER_ASSIGNMENTS)
        return cls(game=game, controller_assignments=assignments, seed=seed)

    @classmethod
    def from_generated_game(
        cls,
        generated_game: GeneratedGame,
        *,
        seed: int | None = None,
        controller_assignments: dict[PlayerRole, str] | None = None,
    ) -> CodenamesSession:
        assignments = dict(controller_assignments or DEFAULT_CONTROLLER_ASSIGNMENTS)
        return cls(
            game=initialize_game(generated_game),
            controller_assignments=assignments,
            seed=seed,
        )

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
        return self.game.give_clue(self.game.active_player, word, number)

    def submit_guess(self, guessed_word: str) -> GuessEvent:
        return self.game.guess(self.game.active_player, guessed_word)

    def submit_pass(self) -> PassEvent:
        return self.game.pass_turn(self.game.active_player)

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": 1,
            "seed": self.seed,
            "default_save_path": str(self.default_save_path) if self.default_save_path else None,
            "controller_assignments": {
                role.value: controller for role, controller in self.controller_assignments.items()
            },
            "game": serialize_game(self.game),
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> CodenamesSession:
        controller_assignments = {
            PlayerRole(role): controller
            for role, controller in payload["controller_assignments"].items()
        }
        default_save_path = payload.get("default_save_path")
        return cls(
            game=deserialize_game(payload["game"]),
            controller_assignments=controller_assignments,
            seed=payload.get("seed"),
            default_save_path=Path(default_save_path) if default_save_path else None,
        )


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
