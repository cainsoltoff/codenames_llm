from __future__ import annotations

import argparse
import sys
from typing import Sequence

from codenames_llm.cli import render_game
from codenames_llm.game import CodenamesError, Team, generate_game, load_words


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="codenames_llm")
    subparsers = parser.add_subparsers(dest="command", required=True)

    new_game = subparsers.add_parser("new-game", help="Generate a new Codenames board.")
    new_game.add_argument(
        "--starts",
        type=Team,
        choices=tuple(Team),
        required=True,
        help="Which team starts and therefore gets the extra agent.",
    )
    new_game.add_argument(
        "--seed",
        type=int,
        help="Optional RNG seed for reproducible game generation.",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command != "new-game":
        parser.error(f"Unsupported command: {args.command}")

    try:
        words = load_words()
        game = generate_game(args.starts, seed=args.seed, words=words)
    except CodenamesError as error:
        print(f"Error: {error}", file=sys.stderr)
        return 1

    print(render_game(game))
    return 0


def cli() -> None:
    raise SystemExit(main())


if __name__ == "__main__":
    cli()
