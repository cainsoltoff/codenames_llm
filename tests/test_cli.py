from __future__ import annotations

import pytest

from codenames_llm.__main__ import main
from codenames_llm.game import CodenamesError


def test_new_game_cli_prints_board_and_key(capsys: pytest.CaptureFixture[str]) -> None:
    exit_code = main(["new-game", "--starts", "red", "--seed", "11"])

    captured = capsys.readouterr()

    assert exit_code == 0
    assert "Public board:" in captured.out
    assert "Hidden key (red starts):" in captured.out
    assert captured.err == ""


def test_new_game_cli_is_seeded(capsys: pytest.CaptureFixture[str]) -> None:
    main(["new-game", "--starts", "blue", "--seed", "22"])
    first = capsys.readouterr().out

    main(["new-game", "--starts", "blue", "--seed", "22"])
    second = capsys.readouterr().out

    assert first == second


def test_invalid_starting_team_is_rejected() -> None:
    with pytest.raises(SystemExit) as excinfo:
        main(["new-game", "--starts", "green"])

    assert excinfo.value.code == 2


def test_word_list_errors_are_reported(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    def fail_loader() -> tuple[str, ...]:
        raise CodenamesError("bad word list")

    monkeypatch.setattr("codenames_llm.__main__.load_words", fail_loader)

    exit_code = main(["new-game", "--starts", "red"])
    captured = capsys.readouterr()

    assert exit_code == 1
    assert captured.out == ""
    assert "bad word list" in captured.err
