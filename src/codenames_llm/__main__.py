from __future__ import annotations

import argparse
from pathlib import Path
import sys
from typing import Sequence

from codenames_llm.cli import render_game
from codenames_llm.game import CodenamesError, PlayerRole, Team, generate_game, load_words
from codenames_llm.session import CodenamesSession, ControllerKind
from codenames_llm.terminal import run_human_session


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="codenames_llm")
    subparsers = parser.add_subparsers(dest="command", required=True)

    new_game = subparsers.add_parser("new-game", help="Generate a new Codenames board.")
    _add_shared_game_arguments(new_game, require_starts=True)

    play = subparsers.add_parser("play", help="Play a Codenames game in the terminal.")
    _add_shared_game_arguments(play, require_starts=False)
    play.add_argument(
        "--load",
        type=Path,
        help="Load and resume a previously saved session JSON file.",
    )
    play.add_argument(
        "--save",
        type=Path,
        help="Default path for saving the session during interactive play.",
    )
    for player_role in PlayerRole:
        play.add_argument(
            f"--{player_role.value}",
            dest=player_role.value,
            choices=[ControllerKind.HUMAN],
            default=ControllerKind.HUMAN,
            help=f"Controller for {player_role.value}. Only 'human' is supported right now.",
        )
    return parser


def _add_shared_game_arguments(
    parser: argparse.ArgumentParser, *, require_starts: bool
) -> None:
    parser.add_argument(
        "--starts",
        type=Team,
        choices=tuple(Team),
        required=require_starts,
        help="Which team starts and therefore gets the extra agent.",
    )
    parser.add_argument(
        "--seed",
        type=int,
        help="Optional RNG seed for reproducible game generation.",
    )


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "new-game":
        return _run_new_game(args)
    if args.command == "play":
        return _run_play(args, parser)

    parser.error(f"Unsupported command: {args.command}")


def _run_new_game(args: argparse.Namespace) -> int:
    try:
        words = load_words()
        game = generate_game(args.starts, seed=args.seed, words=words)
    except CodenamesError as error:
        print(f"Error: {error}", file=sys.stderr)
        return 1

    print(render_game(game))
    return 0


def _run_play(args: argparse.Namespace, parser: argparse.ArgumentParser) -> int:
    controller_assignments = {
        player_role: getattr(args, player_role.value) for player_role in PlayerRole
    }

    if args.load is not None:
        if args.starts is not None or args.seed is not None:
            parser.error("--load cannot be combined with --starts or --seed.")
        session = CodenamesSession.load(args.load)
    else:
        if args.starts is None:
            parser.error("--starts is required when not using --load.")
        session = CodenamesSession.new(
            starting_team=args.starts,
            seed=args.seed,
            controller_assignments=controller_assignments,
        )

    session.controller_assignments = controller_assignments
    if args.save is not None:
        session.default_save_path = args.save
        session.save()

    return run_human_session(session)


def cli() -> None:
    raise SystemExit(main())


if __name__ == "__main__":
    cli()
