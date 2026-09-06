from __future__ import annotations

import argparse
import sys


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="arch-standard")
    sub = parser.add_subparsers(dest="command")
    check = sub.add_parser("check", help="validate a project against the rule catalog")
    check.add_argument("path", nargs="?", default=".", help="project root (default: cwd)")
    docs = sub.add_parser("docs", help="render ARCHITECTURE_STANDARD.md from the catalog")
    docs.add_argument("--check", action="store_true", help="fail if the committed doc is stale")
    return parser


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    parser = _build_parser()
    if not argv:
        parser.print_help()
        return 0
    if argv[0] not in {"check", "docs", "-h", "--help"}:
        parser.print_usage()
        return 2
    parser.parse_args(argv)
    # subcommand bodies are wired in later tasks
    return 0


def _console_main() -> None:
    sys.exit(main())
