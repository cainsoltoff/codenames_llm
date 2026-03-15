from __future__ import annotations

from importlib import resources

import pytest

from codenames_llm.game import (
    BOARD_CARD_COUNT,
    CardRole,
    CodenamesError,
    Team,
    build_role_layout,
    count_roles,
    generate_game,
    load_words,
)


def test_load_words_ignores_blank_lines(tmp_path) -> None:
    word_file = tmp_path / "words.txt"
    word_file.write_text("\nalpha\n\nbeta\n" + "\n".join(f"word-{i}" for i in range(23)))

    words = load_words(word_file)

    assert len(words) == BOARD_CARD_COUNT
    assert words[:2] == ("alpha", "beta")


def test_load_words_rejects_duplicates(tmp_path) -> None:
    word_file = tmp_path / "words.txt"
    word_file.write_text("\n".join(["alpha", "ALPHA"] + [f"word-{i}" for i in range(23)]))

    with pytest.raises(CodenamesError, match="Duplicate word list entry"):
        load_words(word_file)


def test_load_words_rejects_undersized_lists(tmp_path) -> None:
    word_file = tmp_path / "words.txt"
    word_file.write_text("\n".join(f"word-{i}" for i in range(24)))

    with pytest.raises(CodenamesError, match="at least 25 unique entries"):
        load_words(word_file)


@pytest.mark.parametrize("starting_team", [Team.RED, Team.BLUE])
def test_generate_game_has_expected_card_counts(starting_team: Team) -> None:
    game = generate_game(starting_team, seed=7)
    counts = count_roles(game.cards)

    assert len(game.cards) == BOARD_CARD_COUNT
    assert len(set(game.words)) == BOARD_CARD_COUNT
    assert counts[CardRole.ASSASSIN] == 1
    assert counts[CardRole.BYSTANDER] == 7
    assert counts[starting_team.agent_role] == 9
    assert counts[starting_team.other.agent_role] == 8


def test_generate_game_is_deterministic_for_seed() -> None:
    game_one = generate_game(Team.RED, seed=1234)
    game_two = generate_game(Team.RED, seed=1234)

    assert game_one == game_two


def test_generate_game_changes_with_different_seeds() -> None:
    game_one = generate_game(Team.BLUE, seed=100)
    game_two = generate_game(Team.BLUE, seed=101)

    assert game_one != game_two


def test_build_role_layout_matches_standard_counts() -> None:
    layout = build_role_layout(Team.RED)

    assert len(layout) == BOARD_CARD_COUNT
    assert layout.count(CardRole.RED_AGENT) == 9
    assert layout.count(CardRole.BLUE_AGENT) == 8
    assert layout.count(CardRole.BYSTANDER) == 7
    assert layout.count(CardRole.ASSASSIN) == 1


def test_packaged_word_list_is_large_enough() -> None:
    words = load_words(resources.files("codenames_llm").joinpath("data/words.txt"))

    assert len(words) > BOARD_CARD_COUNT
    assert len(set(words)) == len(words)
