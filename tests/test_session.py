from __future__ import annotations

from io import StringIO
import logging

import pytest

from codenames_llm.__main__ import main
from codenames_llm.cli import render_public_game_board
from codenames_llm.game import (
    BOARD_CARD_COUNT,
    BoardCard,
    CardRole,
    GeneratedGame,
    PlayerRole,
    Team,
)
from codenames_llm.session import CodenamesSession, HumanInputRequiredError
from codenames_llm.terminal import run_human_session


class _FakeResponse:
    def __init__(self, output_parsed) -> None:
        self.output_parsed = output_parsed


class _FakeResponses:
    def __init__(self, outputs) -> None:
        self._outputs = iter(outputs)

    def parse(self, **_: object) -> _FakeResponse:
        return _FakeResponse(next(self._outputs))


class _FakeClient:
    def __init__(self, outputs) -> None:
        self.responses = _FakeResponses(outputs)


class _ClueDecision:
    def __init__(self, word: str, number: int) -> None:
        self.word = word
        self.number = number


class _GuessDecision:
    def __init__(self, action: str, word: str | None = None) -> None:
        self.action = action
        self.word = word


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
    session = CodenamesSession.from_generated_game(
        make_generated_game(),
        seed=42,
        controller_assignments={
            PlayerRole.BLUE_SPYMASTER: {
                "kind": "openai",
                "model": "gpt-5.4",
                "prompt_preset": "aggressive_cluegiver",
            },
        },
    )
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
    assert loaded.controller_assignments[PlayerRole.BLUE_SPYMASTER].kind.value == "openai"
    assert (
        loaded.controller_assignments[PlayerRole.BLUE_SPYMASTER].prompt_preset.value
        == "aggressive_cluegiver"
    )


def test_step_active_role_advances_openai_turn(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "codenames_llm.controllers.openai_controller.create_openai_client",
        lambda: _FakeClient([_ClueDecision("ocean", 1)]),
    )
    session = CodenamesSession.from_generated_game(
        make_generated_game(),
        controller_assignments={
            PlayerRole.RED_SPYMASTER: {"kind": "openai", "model": "gpt-5.4"}
        },
    )

    trace = session.step_active_role()

    assert trace.status == "succeeded"
    assert session.game.phase.value == "guess"
    assert session.game.current_clue is not None
    assert session.game.current_clue.word == "ocean"


def test_openai_request_logging_emits_prompt(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    fake_client = _FakeClient([_ClueDecision("ocean", 1)])
    monkeypatch.setattr(
        "codenames_llm.controllers.openai_controller.create_openai_client",
        lambda: fake_client,
    )
    monkeypatch.setenv("CODENAMES_OPENAI_LOG_PROMPTS", "1")
    session = CodenamesSession.from_generated_game(
        make_generated_game(),
        controller_assignments={
            PlayerRole.RED_SPYMASTER: {
                "kind": "openai",
                "model": "gpt-5.4",
                "prompt_preset": "aggressive_cluegiver",
            }
        },
    )

    with caplog.at_level(logging.INFO, logger="codenames_llm.openai"):
        session.step_active_role()

    assert "OpenAI request:" in caplog.text
    assert "Board (all roles visible)" in caplog.text
    assert "Prompt preset: aggressive_cluegiver" in caplog.text
    assert "OpenAI parsed response:" in caplog.text


def test_run_until_human_or_game_over_stops_after_ai_sequence(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_client = _FakeClient([_ClueDecision("ocean", 1), _GuessDecision("pass")])
    monkeypatch.setattr(
        "codenames_llm.controllers.openai_controller.create_openai_client",
        lambda: fake_client,
    )
    session = CodenamesSession.from_generated_game(
        make_generated_game(),
        controller_assignments={
            PlayerRole.RED_SPYMASTER: {"kind": "openai", "model": "gpt-5.4"},
            PlayerRole.RED_OPERATIVE: {"kind": "openai", "model": "gpt-5.4"},
        },
    )

    steps = session.run_until_human_or_game_over(max_steps=4)

    assert steps == 2
    assert session.game.active_player.value == "blue_spymaster"
    assert session.awaiting_human_input is True


def test_run_until_turn_end_stops_when_turn_changes(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_client = _FakeClient([_ClueDecision("ocean", 1), _GuessDecision("pass")])
    monkeypatch.setattr(
        "codenames_llm.controllers.openai_controller.create_openai_client",
        lambda: fake_client,
    )
    session = CodenamesSession.from_generated_game(
        make_generated_game(),
        controller_assignments={
            PlayerRole.RED_SPYMASTER: {"kind": "openai", "model": "gpt-5.4"},
            PlayerRole.RED_OPERATIVE: {"kind": "openai", "model": "gpt-5.4"},
        },
    )

    steps = session.run_until_turn_end(max_steps=4)

    assert steps == 2
    assert session.game.turn_number == 2
    assert session.game.active_player.value == "blue_spymaster"


def test_run_until_human_rejects_human_turn() -> None:
    session = CodenamesSession.from_generated_game(make_generated_game())

    with pytest.raises(HumanInputRequiredError):
        session.run_until_human_or_game_over()


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
