from __future__ import annotations

from typing import Any

from codenames_llm.game import (
    CardRole,
    ClueEvent,
    CodenamesGame,
    GameCard,
    GuessEvent,
    HistoryEvent,
)
from codenames_llm.session import CodenamesSession

PUBLIC_NEUTRAL_COLOR = "neutral"


def build_session_view(session_id: str, session: CodenamesSession) -> dict[str, Any]:
    game = session.game
    return {
        "session_id": session_id,
        "seed": session.seed,
        "controllers": {
            role.value: controller.to_dict()
            for role, controller in session.controller_assignments.items()
        },
        "active_controller": session.active_controller.to_dict(),
        "awaiting_human_input": session.awaiting_human_input,
        "can_step": session.can_step,
        "game": {
            "status": game.status.value,
            "phase": game.phase.value,
            "round_number": game.round_number,
            "turn_number": game.turn_number,
            "active_team": game.active_team.value,
            "active_player": game.active_player.value,
            "current_clue": (
                {"word": game.current_clue.word, "number": game.current_clue.number}
                if game.current_clue
                else None
            ),
            "guesses_remaining": game.guesses_remaining,
            "winner": game.winner.value if game.winner else None,
            "remaining_agents": {
                "red": game.red_agents_remaining,
                "blue": game.blue_agents_remaining,
            },
        },
        "public_board": build_public_board_view(game),
        "spymaster_board": build_spymaster_board_view(game),
        "history": [build_history_event_view(event) for event in game.history],
        "ai_trace": [trace.to_dict() for trace in session.ai_trace],
    }


def build_public_board_view(game: CodenamesGame) -> dict[str, Any]:
    return {
        "cards": [build_public_card_view(index, card) for index, card in enumerate(game.cards)],
        "rows": build_rows(game.cards, card_builder=build_public_card_view),
    }


def build_spymaster_board_view(game: CodenamesGame) -> dict[str, Any]:
    return {
        "cards": [build_spymaster_card_view(index, card) for index, card in enumerate(game.cards)],
        "rows": build_rows(game.cards, card_builder=build_spymaster_card_view),
    }


def build_rows(
    cards: tuple[GameCard, ...],
    *,
    card_builder: Any,
    width: int = 5,
) -> list[list[dict[str, Any]]]:
    rows: list[list[dict[str, Any]]] = []
    for row_index in range(0, len(cards), width):
        rows.append(
            [
                card_builder(card_index, card)
                for card_index, card in enumerate(cards[row_index : row_index + width], start=row_index)
            ]
        )
    return rows


def build_public_card_view(index: int, card: GameCard) -> dict[str, Any]:
    return {
        "index": index,
        "word": card.word,
        "revealed": card.revealed,
        "role": card.role.value if card.revealed else None,
        "color": role_to_color(card.role) if card.revealed else PUBLIC_NEUTRAL_COLOR,
    }


def build_spymaster_card_view(index: int, card: GameCard) -> dict[str, Any]:
    return {
        "index": index,
        "word": card.word,
        "revealed": card.revealed,
        "role": card.role.value,
        "color": role_to_color(card.role),
    }


def role_to_color(role: CardRole) -> str:
    return {
        CardRole.RED_AGENT: "red",
        CardRole.BLUE_AGENT: "blue",
        CardRole.BYSTANDER: "white",
        CardRole.ASSASSIN: "black",
    }[role]


def build_history_event_view(event: HistoryEvent) -> dict[str, Any]:
    base = {
        "type": "pass",
        "team": event.team.value,
        "player": event.player.value,
        "round_number": event.round_number,
        "turn_number": event.turn_number,
    }
    if isinstance(event, ClueEvent):
        base["type"] = "clue"
        base["clue"] = {"word": event.clue.word, "number": event.clue.number}
    elif isinstance(event, GuessEvent):
        base["type"] = "guess"
        base["guessed_word"] = event.guessed_word
        base["revealed_role"] = event.revealed_role.value
        base["was_correct"] = event.was_correct
        base["ended_turn"] = event.ended_turn
        base["ended_game"] = event.ended_game
    return base
