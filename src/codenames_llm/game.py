from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from importlib import resources
import random
from typing import Iterable, Sequence

BOARD_SIZE = 5
BOARD_CARD_COUNT = BOARD_SIZE * BOARD_SIZE


class CodenamesError(ValueError):
    """Raised when the word list or game setup is invalid."""


class InvalidActionError(CodenamesError):
    """Raised when an action is not legal for the current game state."""


class IllegalClueError(InvalidActionError):
    """Raised when a submitted clue fails validation."""


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


class PlayerRole(StrEnum):
    RED_SPYMASTER = "red_spymaster"
    RED_OPERATIVE = "red_operative"
    BLUE_SPYMASTER = "blue_spymaster"
    BLUE_OPERATIVE = "blue_operative"

    @property
    def team(self) -> Team:
        return Team.RED if self.value.startswith("red_") else Team.BLUE

    @property
    def is_spymaster(self) -> bool:
        return self.value.endswith("spymaster")

    @property
    def is_operative(self) -> bool:
        return self.value.endswith("operative")

    @classmethod
    def spymaster_for(cls, team: Team) -> PlayerRole:
        return cls.RED_SPYMASTER if team is Team.RED else cls.BLUE_SPYMASTER

    @classmethod
    def operative_for(cls, team: Team) -> PlayerRole:
        return cls.RED_OPERATIVE if team is Team.RED else cls.BLUE_OPERATIVE


class GamePhase(StrEnum):
    CLUE = "clue"
    GUESS = "guess"


class GameStatus(StrEnum):
    ONGOING = "ongoing"
    GAME_OVER = "game_over"


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


@dataclass(slots=True)
class GameCard:
    word: str
    role: CardRole
    revealed: bool = False


@dataclass(frozen=True, slots=True)
class Clue:
    word: str
    number: int


@dataclass(frozen=True, slots=True)
class ClueEvent:
    team: Team
    player: PlayerRole
    clue: Clue
    round_number: int
    turn_number: int


@dataclass(frozen=True, slots=True)
class GuessEvent:
    team: Team
    player: PlayerRole
    guessed_word: str
    revealed_role: CardRole
    was_correct: bool
    ended_turn: bool
    ended_game: bool
    round_number: int
    turn_number: int


@dataclass(frozen=True, slots=True)
class PassEvent:
    team: Team
    player: PlayerRole
    round_number: int
    turn_number: int


HistoryEvent = ClueEvent | GuessEvent | PassEvent


@dataclass(slots=True)
class CodenamesGame:
    starting_team: Team
    cards: tuple[GameCard, ...]
    active_team: Team
    active_player: PlayerRole
    round_number: int
    turn_number: int
    phase: GamePhase
    status: GameStatus
    red_agents_remaining: int
    blue_agents_remaining: int
    current_clue: Clue | None = None
    guesses_remaining: int | None = None
    winner: Team | None = None
    history: list[HistoryEvent] = field(default_factory=list)

    def rows(self) -> tuple[tuple[GameCard, ...], ...]:
        return tuple(
            self.cards[index : index + BOARD_SIZE]
            for index in range(0, BOARD_CARD_COUNT, BOARD_SIZE)
        )

    @property
    def words(self) -> tuple[str, ...]:
        return tuple(card.word for card in self.cards)

    def give_clue(self, player: PlayerRole, word: str, number: int) -> ClueEvent:
        self._ensure_ongoing()
        self._ensure_phase(GamePhase.CLUE)
        self._ensure_active_player(player)

        clue = validate_clue(word, number, self.words)
        self.current_clue = clue
        self.guesses_remaining = clue.number + 1
        self.phase = GamePhase.GUESS
        self.active_player = PlayerRole.operative_for(self.active_team)

        event = ClueEvent(
            team=self.active_team,
            player=player,
            clue=clue,
            round_number=self.round_number,
            turn_number=self.turn_number,
        )
        self.history.append(event)
        return event

    def guess(self, player: PlayerRole, guessed_word: str) -> GuessEvent:
        self._ensure_ongoing()
        self._ensure_phase(GamePhase.GUESS)
        self._ensure_active_player(player)
        if self.current_clue is None or self.guesses_remaining is None:
            msg = "Cannot guess before a clue has been given."
            raise InvalidActionError(msg)

        action_round = self.round_number
        action_turn = self.turn_number
        card = self._card_for_word(guessed_word)
        if card.revealed:
            msg = f"Card {guessed_word!r} has already been revealed."
            raise InvalidActionError(msg)

        card.revealed = True
        self._decrement_remaining_agents(card.role)

        was_correct = card.role is self.active_team.agent_role
        ended_turn = False
        ended_game = False

        winning_team = self._winning_team_after_reveal(card.role)
        if winning_team is not None:
            self._finish_game(winning_team)
            ended_turn = True
            ended_game = True
        elif was_correct:
            self.guesses_remaining -= 1
            if self.guesses_remaining == 0:
                ended_turn = True
                self._advance_turn()
        else:
            ended_turn = True
            self._advance_turn()

        event = GuessEvent(
            team=player.team,
            player=player,
            guessed_word=card.word,
            revealed_role=card.role,
            was_correct=was_correct,
            ended_turn=ended_turn,
            ended_game=ended_game,
            round_number=action_round,
            turn_number=action_turn,
        )
        self.history.append(event)
        return event

    def pass_turn(self, player: PlayerRole) -> PassEvent:
        self._ensure_ongoing()
        self._ensure_phase(GamePhase.GUESS)
        self._ensure_active_player(player)

        event = PassEvent(
            team=self.active_team,
            player=player,
            round_number=self.round_number,
            turn_number=self.turn_number,
        )
        self.history.append(event)
        self._advance_turn()
        return event

    def _ensure_ongoing(self) -> None:
        if self.status is GameStatus.GAME_OVER:
            msg = "No actions are allowed after the game is over."
            raise InvalidActionError(msg)

    def _ensure_phase(self, expected_phase: GamePhase) -> None:
        if self.phase is not expected_phase:
            msg = f"Action is only allowed during the {expected_phase.value} phase."
            raise InvalidActionError(msg)

    def _ensure_active_player(self, player: PlayerRole) -> None:
        if player is not self.active_player:
            msg = f"It is currently {self.active_player.value}'s turn to act."
            raise InvalidActionError(msg)

    def _card_for_word(self, guessed_word: str) -> GameCard:
        normalized_guess = guessed_word.strip().casefold()
        for card in self.cards:
            if card.word.casefold() == normalized_guess:
                return card

        msg = f"Board does not contain a card named {guessed_word!r}."
        raise InvalidActionError(msg)

    def _decrement_remaining_agents(self, revealed_role: CardRole) -> None:
        if revealed_role is CardRole.RED_AGENT:
            self.red_agents_remaining -= 1
        elif revealed_role is CardRole.BLUE_AGENT:
            self.blue_agents_remaining -= 1

    def _winning_team_after_reveal(self, revealed_role: CardRole) -> Team | None:
        if revealed_role is CardRole.ASSASSIN:
            return self.active_team.other
        if self.red_agents_remaining == 0:
            return Team.RED
        if self.blue_agents_remaining == 0:
            return Team.BLUE
        return None

    def _finish_game(self, winning_team: Team) -> None:
        self.status = GameStatus.GAME_OVER
        self.winner = winning_team
        self.phase = GamePhase.GUESS
        self.guesses_remaining = 0

    def _advance_turn(self) -> None:
        completed_team = self.active_team
        if completed_team is self.starting_team.other:
            self.round_number += 1

        self.active_team = completed_team.other
        self.active_player = PlayerRole.spymaster_for(self.active_team)
        self.phase = GamePhase.CLUE
        self.current_clue = None
        self.guesses_remaining = None
        self.turn_number += 1


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


def initialize_game(generated_game: GeneratedGame) -> CodenamesGame:
    counts = count_roles(generated_game.cards)
    cards = tuple(GameCard(word=card.word, role=card.role) for card in generated_game.cards)
    return CodenamesGame(
        starting_team=generated_game.starting_team,
        cards=cards,
        active_team=generated_game.starting_team,
        active_player=PlayerRole.spymaster_for(generated_game.starting_team),
        round_number=1,
        turn_number=1,
        phase=GamePhase.CLUE,
        status=GameStatus.ONGOING,
        red_agents_remaining=counts[CardRole.RED_AGENT],
        blue_agents_remaining=counts[CardRole.BLUE_AGENT],
    )


def validate_clue(word: str, number: int, board_words: Sequence[str]) -> Clue:
    stripped_word = word.strip()
    if not stripped_word or any(character.isspace() for character in stripped_word):
        msg = "Clue word must be a single word."
        raise IllegalClueError(msg)
    if number <= 0:
        msg = "Clue number must be a positive integer."
        raise IllegalClueError(msg)

    normalized_clue = normalize_for_overlap(stripped_word)
    if not normalized_clue:
        msg = "Clue word must contain letters or numbers."
        raise IllegalClueError(msg)

    for board_word in board_words:
        normalized_board_word = normalize_for_overlap(board_word)
        if normalized_clue == normalized_board_word:
            msg = f"Clue {stripped_word!r} exactly matches board word {board_word!r}."
            raise IllegalClueError(msg)
        if normalized_clue in normalized_board_word or normalized_board_word in normalized_clue:
            msg = f"Clue {stripped_word!r} overlaps with board word {board_word!r}."
            raise IllegalClueError(msg)

    return Clue(word=stripped_word, number=number)


def normalize_for_overlap(value: str) -> str:
    return "".join(character for character in value.casefold() if character.isalnum())


def count_roles(cards: Iterable[BoardCard | GameCard]) -> dict[CardRole, int]:
    counts = {role: 0 for role in CardRole}
    for card in cards:
        counts[card.role] += 1
    return counts
