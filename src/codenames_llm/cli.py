from __future__ import annotations

from codenames_llm.game import BoardCard, GeneratedGame


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
        formatted_cells = [
            f"{card.word} [{card.role.short_label}]".ljust(width + 4) for card in row
        ]
        rows.append("".join(formatted_cells).rstrip())
    return "\n".join(rows)


def render_game(game: GeneratedGame) -> str:
    return f"{render_public_board(game)}\n\n{render_key_board(game)}"
