from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from importlib import resources
import random
from typing import Iterable, Sequence

BOARD_SIZE = 5
BOARD_CARD_COUNT = BOARD_SIZE * BOARD_SIZE


class CodenamesError(ValueError):
    """Raised when the word list or game setup is invalid."""


class Team(StrEnum):
    RED = "red"
    BLUE = "blue"

    @property
    def agent_role(self) -> CardRole:
        return CardRole.RED_AGENT if self is Team.RED else CardRole.BLUE_AGENT

    @property
    def other(self) -> Team:
        return Team.BLUE if self is Team.RED else Team.RED


class CardRole(StrEnum):
    RED_AGENT = "red_agent"
    BLUE_AGENT = "blue_agent"
    BYSTANDER = "bystander"
    ASSASSIN = "assassin"

    @property
    def short_label(self) -> str:
        return {
            CardRole.RED_AGENT: "R",
            CardRole.BLUE_AGENT: "B",
            CardRole.BYSTANDER: "I",
            CardRole.ASSASSIN: "A",
        }[self]


@dataclass(frozen=True, slots=True)
class BoardCard:
    word: str
    role: CardRole


@dataclass(frozen=True, slots=True)
class GeneratedGame:
    starting_team: Team
    cards: tuple[BoardCard, ...]

    def __post_init__(self) -> None:
        if len(self.cards) != BOARD_CARD_COUNT:
            msg = f"A game must contain exactly {BOARD_CARD_COUNT} cards."
            raise CodenamesError(msg)

    @property
    def words(self) -> tuple[str, ...]:
        return tuple(card.word for card in self.cards)

    def rows(self) -> tuple[tuple[BoardCard, ...], ...]:
        return tuple(
            self.cards[index : index + BOARD_SIZE]
            for index in range(0, BOARD_CARD_COUNT, BOARD_SIZE)
        )


def load_words(word_source: resources.abc.Traversable | None = None) -> tuple[str, ...]:
    source = word_source or resources.files("codenames_llm").joinpath("data/words.txt")
    raw_words = source.read_text(encoding="utf-8").splitlines()

    unique_words: list[str] = []
    seen: dict[str, str] = {}
    for line_number, raw_word in enumerate(raw_words, start=1):
        word = raw_word.strip()
        if not word:
            continue

        normalized = word.casefold()
        previous = seen.get(normalized)
        if previous is not None:
            msg = (
                f"Duplicate word list entry at line {line_number}: {word!r} "
                f"duplicates {previous!r}."
            )
            raise CodenamesError(msg)

        seen[normalized] = word
        unique_words.append(word)

    if len(unique_words) < BOARD_CARD_COUNT:
        msg = (
            "Word list must contain at least "
            f"{BOARD_CARD_COUNT} unique entries; found {len(unique_words)}."
        )
        raise CodenamesError(msg)

    return tuple(unique_words)


def build_role_layout(starting_team: Team) -> tuple[CardRole, ...]:
    roles = [starting_team.agent_role] * 9
    roles.extend([starting_team.other.agent_role] * 8)
    roles.extend([CardRole.BYSTANDER] * 7)
    roles.append(CardRole.ASSASSIN)
    return tuple(roles)


def generate_game(
    starting_team: Team,
    *,
    seed: int | None = None,
    words: Sequence[str] | None = None,
) -> GeneratedGame:
    available_words = tuple(words) if words is not None else load_words()
    if len(set(available_words)) < BOARD_CARD_COUNT:
        msg = "Game generation requires at least 25 unique words."
        raise CodenamesError(msg)

    rng = random.Random(seed)
    selected_words = rng.sample(available_words, k=BOARD_CARD_COUNT)
    rng.shuffle(selected_words)

    roles = list(build_role_layout(starting_team))
    rng.shuffle(roles)

    cards = tuple(
        BoardCard(word=word, role=role) for word, role in zip(selected_words, roles, strict=True)
    )
    return GeneratedGame(starting_team=starting_team, cards=cards)


def count_roles(cards: Iterable[BoardCard]) -> dict[CardRole, int]:
    counts = {role: 0 for role in CardRole}
    for card in cards:
        counts[card.role] += 1
    return counts
