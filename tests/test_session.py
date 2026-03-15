from __future__ import annotations

from io import StringIO

from codenames_llm.__main__ import main
from codenames_llm.cli import render_public_game_board
from codenames_llm.game import BOARD_CARD_COUNT, BoardCard, CardRole, GeneratedGame, Team
from codenames_llm.session import CodenamesSession
from codenames_llm.terminal import run_human_session


def make_generated_game(starting_team: Team = Team.RED) -> GeneratedGame:
    roles = [CardRole.RED_AGENT, CardRole.BLUE_AGENT]
    roles.extend([CardRole.BYSTANDER] * 22)
    roles.append(CardRole.ASSASSIN)
    cards = tuple(
        BoardCard(word=f"card-{index:02d}", role=role) for index, role in enumerate(roles)
    )
    assert len(cards) == BOARD_CARD_COUNT
    return GeneratedGame(starting_team=starting_team, cards=cards)


def test_public_board_uses_neutral_color_for_unrevealed_cards() -> None:
    session = CodenamesSession.from_generated_game(make_generated_game())
    session.submit_clue("ocean", 1)
    session.submit_guess("card-00")

    rendered = render_public_game_board(session.game)

    assert "\033[33m" in rendered
    assert "\033[31m" in rendered
    assert "card-00" in rendered
    assert "card-01" in rendered


def test_session_save_and_load_round_trip(tmp_path) -> None:
    session = CodenamesSession.from_generated_game(make_generated_game(), seed=42)
    session.default_save_path = tmp_path / "saved-session.json"
    session.submit_clue("ocean", 1)
    session.submit_guess("card-00")

    saved_path = session.save()
    loaded = CodenamesSession.load(saved_path)

    assert loaded.seed == 42
    assert loaded.game.turn_number == session.game.turn_number
    assert loaded.game.active_team == session.game.active_team
    assert loaded.game.history == session.game.history
    assert loaded.default_save_path == saved_path


def test_run_human_session_can_complete_a_game() -> None:
    session = CodenamesSession.from_generated_game(make_generated_game())
    inputs = iter(["ocean 1", "card-00"])
    output = StringIO()

    exit_code = run_human_session(session, input_fn=lambda _: next(inputs), output=output)
    transcript = output.getvalue()

    assert exit_code == 0
    assert "Starting Codenames session." in transcript
    assert "red_spymaster gave clue ocean 1." in transcript
    assert "Game over. Winner: red" in transcript


def test_play_command_can_save_initial_session(monkeypatch, tmp_path) -> None:
    save_path = tmp_path / "cli-session.json"
    captured = {}

    def fake_runner(session: CodenamesSession) -> int:
        captured["path"] = session.default_save_path
        return 0

    monkeypatch.setattr("codenames_llm.__main__.run_human_session", fake_runner)

    exit_code = main(["play", "--starts", "red", "--seed", "7", "--save", str(save_path)])

    assert exit_code == 0
    assert captured["path"] == save_path
    assert save_path.exists()
