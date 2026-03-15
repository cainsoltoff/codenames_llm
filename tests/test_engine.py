from __future__ import annotations

import pytest

from codenames_llm.game import (
    BOARD_CARD_COUNT,
    BoardCard,
    CardRole,
    ClueEvent,
    GamePhase,
    GameStatus,
    GeneratedGame,
    GuessEvent,
    IllegalClueError,
    InvalidActionError,
    PassEvent,
    PlayerRole,
    Team,
    build_role_layout,
    initialize_game,
)


def make_generated_game(starting_team: Team = Team.RED) -> GeneratedGame:
    words = [f"word-{index:02d}" for index in range(BOARD_CARD_COUNT)]
    cards = tuple(
        BoardCard(word=word, role=role)
        for word, role in zip(words, build_role_layout(starting_team), strict=True)
    )
    return GeneratedGame(starting_team=starting_team, cards=cards)


def make_sudden_death_game() -> GeneratedGame:
    roles = [CardRole.RED_AGENT, CardRole.BLUE_AGENT]
    roles.extend([CardRole.BYSTANDER] * 22)
    roles.append(CardRole.ASSASSIN)
    cards = tuple(
        BoardCard(word=f"card-{index:02d}", role=role) for index, role in enumerate(roles)
    )
    return GeneratedGame(starting_team=Team.RED, cards=cards)


def test_initialize_game_starts_in_clue_phase() -> None:
    game = initialize_game(make_generated_game(Team.RED))

    assert game.active_team == Team.RED
    assert game.active_player == PlayerRole.RED_SPYMASTER
    assert game.phase == GamePhase.CLUE
    assert game.round_number == 1
    assert game.turn_number == 1
    assert game.red_agents_remaining == 9
    assert game.blue_agents_remaining == 8
    assert game.status == GameStatus.ONGOING


def test_give_clue_moves_to_guess_phase_and_records_history() -> None:
    game = initialize_game(make_generated_game())

    event = game.give_clue(PlayerRole.RED_SPYMASTER, "ocean", 2)

    assert event == ClueEvent(
        team=Team.RED,
        player=PlayerRole.RED_SPYMASTER,
        clue=game.current_clue,
        round_number=1,
        turn_number=1,
    )
    assert game.current_clue is not None
    assert game.current_clue.word == "ocean"
    assert game.current_clue.number == 2
    assert game.guesses_remaining == 3
    assert game.phase == GamePhase.GUESS
    assert game.active_player == PlayerRole.RED_OPERATIVE
    assert game.history == [event]


@pytest.mark.parametrize(
    ("word", "number", "match"),
    [
        ("two words", 1, "single word"),
        ("word-00", 1, "exactly matches"),
        ("word", 1, "overlaps"),
        ("ocean", 0, "positive integer"),
    ],
)
def test_illegal_clues_are_rejected(word: str, number: int, match: str) -> None:
    game = initialize_game(make_generated_game())

    with pytest.raises(IllegalClueError, match=match):
        game.give_clue(PlayerRole.RED_SPYMASTER, word, number)


def test_wrong_player_cannot_act() -> None:
    game = initialize_game(make_generated_game())

    with pytest.raises(InvalidActionError, match="red_spymaster"):
        game.give_clue(PlayerRole.BLUE_SPYMASTER, "ocean", 1)


def test_correct_guess_can_continue_turn() -> None:
    game = initialize_game(make_generated_game())
    game.give_clue(PlayerRole.RED_SPYMASTER, "ocean", 1)

    event = game.guess(PlayerRole.RED_OPERATIVE, "word-00")

    assert event == GuessEvent(
        team=Team.RED,
        player=PlayerRole.RED_OPERATIVE,
        guessed_word="word-00",
        revealed_role=CardRole.RED_AGENT,
        was_correct=True,
        ended_turn=False,
        ended_game=False,
        round_number=1,
        turn_number=1,
    )
    assert game.cards[0].revealed is True
    assert game.red_agents_remaining == 8
    assert game.phase == GamePhase.GUESS
    assert game.active_player == PlayerRole.RED_OPERATIVE
    assert game.guesses_remaining == 1


def test_turn_ends_after_guess_limit_is_used() -> None:
    game = initialize_game(make_generated_game())
    game.give_clue(PlayerRole.RED_SPYMASTER, "ocean", 1)
    game.guess(PlayerRole.RED_OPERATIVE, "word-00")

    event = game.guess(PlayerRole.RED_OPERATIVE, "word-01")

    assert event.ended_turn is True
    assert event.ended_game is False
    assert game.active_team == Team.BLUE
    assert game.active_player == PlayerRole.BLUE_SPYMASTER
    assert game.phase == GamePhase.CLUE
    assert game.current_clue is None
    assert game.guesses_remaining is None
    assert game.round_number == 1
    assert game.turn_number == 2


def test_wrong_team_guess_ends_turn() -> None:
    game = initialize_game(make_generated_game())
    game.give_clue(PlayerRole.RED_SPYMASTER, "ocean", 1)

    event = game.guess(PlayerRole.RED_OPERATIVE, "word-09")

    assert event.revealed_role == CardRole.BLUE_AGENT
    assert event.was_correct is False
    assert event.ended_turn is True
    assert game.blue_agents_remaining == 7
    assert game.active_team == Team.BLUE
    assert game.active_player == PlayerRole.BLUE_SPYMASTER


def test_bystander_guess_ends_turn() -> None:
    game = initialize_game(make_generated_game())
    game.give_clue(PlayerRole.RED_SPYMASTER, "ocean", 1)

    event = game.guess(PlayerRole.RED_OPERATIVE, "word-17")

    assert event.revealed_role == CardRole.BYSTANDER
    assert event.was_correct is False
    assert event.ended_turn is True
    assert game.active_team == Team.BLUE


def test_assassin_guess_ends_game() -> None:
    game = initialize_game(make_generated_game())
    game.give_clue(PlayerRole.RED_SPYMASTER, "ocean", 1)

    event = game.guess(PlayerRole.RED_OPERATIVE, "word-24")

    assert event.revealed_role == CardRole.ASSASSIN
    assert event.ended_game is True
    assert game.status == GameStatus.GAME_OVER
    assert game.winner == Team.BLUE


def test_revealing_final_agent_wins_immediately() -> None:
    game = initialize_game(make_sudden_death_game())
    game.give_clue(PlayerRole.RED_SPYMASTER, "ocean", 1)

    event = game.guess(PlayerRole.RED_OPERATIVE, "card-00")

    assert event.ended_game is True
    assert game.status == GameStatus.GAME_OVER
    assert game.winner == Team.RED


def test_revealed_card_cannot_be_guessed_again() -> None:
    game = initialize_game(make_generated_game())
    game.give_clue(PlayerRole.RED_SPYMASTER, "ocean", 2)
    game.guess(PlayerRole.RED_OPERATIVE, "word-00")

    with pytest.raises(InvalidActionError, match="already been revealed"):
        game.guess(PlayerRole.RED_OPERATIVE, "word-00")


def test_pass_turn_hands_control_to_other_team() -> None:
    game = initialize_game(make_generated_game())
    game.give_clue(PlayerRole.RED_SPYMASTER, "ocean", 1)

    event = game.pass_turn(PlayerRole.RED_OPERATIVE)

    assert event == PassEvent(
        team=Team.RED,
        player=PlayerRole.RED_OPERATIVE,
        round_number=1,
        turn_number=1,
    )
    assert game.active_team == Team.BLUE
    assert game.active_player == PlayerRole.BLUE_SPYMASTER
    assert game.phase == GamePhase.CLUE


def test_round_advances_after_both_teams_finish_turns() -> None:
    game = initialize_game(make_generated_game())
    game.give_clue(PlayerRole.RED_SPYMASTER, "ocean", 1)
    game.pass_turn(PlayerRole.RED_OPERATIVE)
    game.give_clue(PlayerRole.BLUE_SPYMASTER, "river", 1)
    game.pass_turn(PlayerRole.BLUE_OPERATIVE)

    assert game.active_team == Team.RED
    assert game.active_player == PlayerRole.RED_SPYMASTER
    assert game.round_number == 2
    assert game.turn_number == 3


def test_no_actions_allowed_after_game_over() -> None:
    game = initialize_game(make_generated_game())
    game.give_clue(PlayerRole.RED_SPYMASTER, "ocean", 1)
    game.guess(PlayerRole.RED_OPERATIVE, "word-24")

    with pytest.raises(InvalidActionError, match="game is over"):
        game.pass_turn(PlayerRole.RED_OPERATIVE)


def test_history_records_clue_guess_and_pass_events_in_order() -> None:
    game = initialize_game(make_generated_game())

    clue_event = game.give_clue(PlayerRole.RED_SPYMASTER, "ocean", 2)
    guess_event = game.guess(PlayerRole.RED_OPERATIVE, "word-00")
    pass_event = game.pass_turn(PlayerRole.RED_OPERATIVE)

    assert game.history == [clue_event, guess_event, pass_event]
