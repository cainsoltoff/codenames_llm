from __future__ import annotations

from codenames_llm.game import BoardCard, CardRole, GeneratedGame

ANSI_RESET = "\033[0m"
ANSI_RED = "\033[31m"
ANSI_BLUE = "\033[34m"
ANSI_WHITE = "\033[37m"
ANSI_BLACK_BACKGROUND = "\033[40m"


def _role_color(role: CardRole) -> str:
    return {
        CardRole.RED_AGENT: ANSI_RED,
        CardRole.BLUE_AGENT: ANSI_BLUE,
        CardRole.BYSTANDER: ANSI_WHITE,
        CardRole.ASSASSIN: f"{ANSI_WHITE}{ANSI_BLACK_BACKGROUND}",
    }[role]


def _format_key_cell(card: BoardCard, width: int) -> str:
    padded_word = card.word.ljust(width)
    return f"{_role_color(card.role)}{padded_word}{ANSI_RESET}"


def _column_width(cards: tuple[BoardCard, ...]) -> int:
    longest_word = max(len(card.word) for card in cards)
    return max(longest_word + 2, 12)


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


def render_game(game: GeneratedGame) -> str:
    return f"{render_public_board(game)}\n\n{render_key_board(game)}"
