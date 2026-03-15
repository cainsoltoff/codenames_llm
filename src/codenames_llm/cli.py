from __future__ import annotations

from codenames_llm.game import (
    BoardCard,
    CardRole,
    ClueEvent,
    CodenamesGame,
    GameCard,
    GeneratedGame,
    GuessEvent,
    HistoryEvent,
)

ANSI_RESET = "\033[0m"
ANSI_RED = "\033[31m"
ANSI_BLUE = "\033[34m"
ANSI_WHITE = "\033[37m"
ANSI_YELLOW = "\033[33m"
ANSI_BLACK_BACKGROUND = "\033[40m"


def _role_color(role: CardRole) -> str:
    return {
        CardRole.RED_AGENT: ANSI_RED,
        CardRole.BLUE_AGENT: ANSI_BLUE,
        CardRole.BYSTANDER: ANSI_WHITE,
        CardRole.ASSASSIN: f"{ANSI_WHITE}{ANSI_BLACK_BACKGROUND}",
    }[role]


def _colorize(text: str, color: str) -> str:
    return f"{color}{text}{ANSI_RESET}"


def _column_width(cards: tuple[BoardCard, ...] | tuple[GameCard, ...]) -> int:
    longest_word = max(len(card.word) for card in cards)
    return max(longest_word + 2, 12)


def _format_key_cell(card: BoardCard | GameCard, width: int) -> str:
    padded_word = card.word.ljust(width)
    return _colorize(padded_word, _role_color(card.role))


def _format_public_cell(card: GameCard, width: int) -> str:
    padded_word = card.word.ljust(width)
    if card.revealed:
        return _colorize(padded_word, _role_color(card.role))
    return _colorize(padded_word, ANSI_YELLOW)


def render_public_board(game: GeneratedGame) -> str:
    width = _column_width(game.cards)
    rows = ["Public board:"]
    for row in game.rows():
        rows.append("".join(card.word.ljust(width) for card in row).rstrip())
    return "\n".join(rows)


def render_key_board(game: GeneratedGame) -> str:
    width = _column_width(game.cards)
    rows = [f"Hidden key ({game.starting_team.value} starts):"]
    for row in game.rows():
        formatted_cells = [_format_key_cell(card, width) for card in row]
        rows.append("".join(formatted_cells).rstrip())
    return "\n".join(rows)


def render_public_game_board(game: CodenamesGame) -> str:
    width = _column_width(game.cards)
    rows = ["Public board:"]
    for row in game.rows():
        rows.append("".join(_format_public_cell(card, width) for card in row).rstrip())
    return "\n".join(rows)


def render_spymaster_board(game: CodenamesGame) -> str:
    width = _column_width(game.cards)
    rows = [f"Spymaster board ({game.starting_team.value} starts):"]
    for row in game.rows():
        rows.append("".join(_format_key_cell(card, width) for card in row).rstrip())
    return "\n".join(rows)


def render_status(game: CodenamesGame) -> str:
    current_clue = (
        f"{game.current_clue.word} {game.current_clue.number}" if game.current_clue else "none"
    )
    guesses_remaining = (
        str(game.guesses_remaining) if game.guesses_remaining is not None else "n/a"
    )
    winner = game.winner.value if game.winner else "n/a"
    return "\n".join(
        [
            "Status:",
            f"Round: {game.round_number}  Turn: {game.turn_number}",
            f"Active team: {game.active_team.value}  Active role: {game.active_player.value}",
            f"Phase: {game.phase.value}  Game status: {game.status.value}",
            f"Current clue: {current_clue}  Guesses remaining: {guesses_remaining}",
            (
                "Agents remaining: "
                f"red={game.red_agents_remaining} blue={game.blue_agents_remaining}"
            ),
            f"Winner: {winner}",
        ]
    )


def render_history(history: list[HistoryEvent], *, limit: int = 5) -> str:
    if not history:
        return "History:\nNo actions yet."

    rows = ["History:"]
    for event in history[-limit:]:
        rows.append(_format_history_event(event))
    return "\n".join(rows)


def _format_history_event(event: HistoryEvent) -> str:
    prefix = f"[R{event.round_number} T{event.turn_number}]"
    if isinstance(event, ClueEvent):
        return (
            f"{prefix} {event.player.value} gave clue "
            f"{event.clue.word} {event.clue.number}"
        )
    if isinstance(event, GuessEvent):
        outcome = "correct" if event.was_correct else "miss"
        ending = " and ended the game" if event.ended_game else (
            " and ended the turn" if event.ended_turn else ""
        )
        return (
            f"{prefix} {event.player.value} guessed {event.guessed_word} "
            f"({event.revealed_role.value}, {outcome}){ending}"
        )
    return f"{prefix} {event.player.value} passed"


def render_game(game: GeneratedGame) -> str:
    return f"{render_public_board(game)}\n\n{render_key_board(game)}"
