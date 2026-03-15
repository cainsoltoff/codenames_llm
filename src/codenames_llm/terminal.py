from __future__ import annotations

from collections.abc import Callable
import sys
from typing import TextIO

from codenames_llm.cli import (
    render_history,
    render_public_game_board,
    render_spymaster_board,
    render_status,
)
from codenames_llm.game import IllegalClueError, InvalidActionError
from codenames_llm.session import CodenamesSession


InputFn = Callable[[str], str]


def run_human_session(
    session: CodenamesSession,
    *,
    input_fn: InputFn = input,
    output: TextIO | None = None,
) -> int:
    stream = output or sys.stdout
    _write(stream, "Starting Codenames session.")

    while True:
        _write(stream, render_status(session.game))
        if session.game.active_player.is_spymaster:
            _write(stream, render_spymaster_board(session.game))
            prompt = "Enter clue as '<word> <number>', or 'save [path]', or 'quit': "
            if _handle_spymaster_turn(session, input_fn=input_fn, output=stream, prompt=prompt):
                break
        else:
            _write(stream, render_public_game_board(session.game))
            _write(stream, render_history(session.game.history))
            prompt = "Enter a guess, 'pass', 'save [path]', or 'quit': "
            if _handle_operative_turn(session, input_fn=input_fn, output=stream, prompt=prompt):
                break

        if session.game.status.value == "game_over":
            _write(stream, render_public_game_board(session.game))
            _write(stream, f"Game over. Winner: {session.game.winner.value}")
            return 0

    _write(stream, "Session ended before game over.")
    return 0


def _handle_spymaster_turn(
    session: CodenamesSession,
    *,
    input_fn: InputFn,
    output: TextIO,
    prompt: str,
) -> bool:
    while True:
        raw_input = input_fn(prompt).strip()
        meta_result = _handle_meta_command(raw_input, session, output)
        if meta_result == "quit":
            return True
        if meta_result == "continue":
            continue

        parts = raw_input.split()
        if len(parts) != 2:
            _write(output, "Enter a clue as exactly two tokens: a word and a positive integer.")
            continue

        clue_word, clue_number_text = parts
        try:
            clue_number = int(clue_number_text)
        except ValueError:
            _write(output, "Clue number must be an integer.")
            continue

        try:
            event = session.submit_clue(clue_word, clue_number)
        except IllegalClueError as error:
            _write(output, f"Illegal clue: {error}")
            continue
        except InvalidActionError as error:
            _write(output, f"Invalid action: {error}")
            continue

        _write(
            output,
            f"{event.player.value} gave clue {event.clue.word} {event.clue.number}.",
        )
        _autosave(session, output)
        return False


def _handle_operative_turn(
    session: CodenamesSession,
    *,
    input_fn: InputFn,
    output: TextIO,
    prompt: str,
) -> bool:
    while True:
        raw_input = input_fn(prompt).strip()
        meta_result = _handle_meta_command(raw_input, session, output)
        if meta_result == "quit":
            return True
        if meta_result == "continue":
            continue
        if raw_input.casefold() == "pass":
            event = session.submit_pass()
            _write(output, f"{event.player.value} passed.")
            _autosave(session, output)
            return False
        if not raw_input:
            _write(output, "Enter a guess, 'pass', 'save [path]', or 'quit'.")
            continue

        try:
            event = session.submit_guess(raw_input)
        except InvalidActionError as error:
            _write(output, f"Invalid action: {error}")
            continue

        result = "correct" if event.was_correct else "incorrect"
        _write(
            output,
            (
                f"{event.player.value} guessed {event.guessed_word}. "
                f"Reveal: {event.revealed_role.value}. Result: {result}."
            ),
        )
        _autosave(session, output)
        return False


def _handle_meta_command(raw_input: str, session: CodenamesSession, output: TextIO) -> str | None:
    lowered = raw_input.casefold()
    if lowered == "quit":
        return "quit"
    if not lowered.startswith("save"):
        return None

    _, _, maybe_path = raw_input.partition(" ")
    save_path = maybe_path.strip() or None
    try:
        saved_path = session.save(save_path)
    except ValueError as error:
        _write(output, str(error))
    else:
        _write(output, f"Saved session to {saved_path}.")
    return "continue"


def _autosave(session: CodenamesSession, output: TextIO) -> None:
    if session.default_save_path is None:
        return
    saved_path = session.save()
    _write(output, f"Autosaved session to {saved_path}.")


def _write(output: TextIO, text: str) -> None:
    print(text, file=output)
