from __future__ import annotations

import argparse
import sys
from pathlib import Path

from arch_standard.checks import all_checks
from arch_standard.checks.adr_waivers import active_waivers
from arch_standard.checks.base import ProjectLayout
from arch_standard.report import Report
from arch_standard.rules.catalog import Catalog

_PACKAGED_RULES = Path(__file__).resolve().parents[2] / "rules"


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="arch-standard")
    sub = parser.add_subparsers(dest="command")
    check = sub.add_parser("check", help="validate a project against the rule catalog")
    check.add_argument("path", nargs="?", default=".", help="project root (default: cwd)")
    docs = sub.add_parser("docs", help="render ARCHITECTURE_STANDARD.md from the catalog")
    docs.add_argument("--check", action="store_true", help="fail if the committed doc is stale")
    return parser


def _run_check(path: str) -> int:
    root = Path(path).resolve()
    layout = ProjectLayout.detect(root)
    rules_dir = root / "rules" if (root / "rules").is_dir() else _PACKAGED_RULES
    catalog = Catalog.load(rules_dir)
    waivers = active_waivers(root / "docs" / "adr")
    report = Report.collect(layout, catalog, all_checks()).with_waivers(waivers)
    print(report.format_text(catalog))
    return report.exit_code(catalog)


def _run_docs(check: bool) -> int:
    # implemented in Task 15
    return 0


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    parser = _build_parser()
    if not argv:
        parser.print_help()
        return 0
    if argv[0] not in {"check", "docs", "-h", "--help"}:
        parser.print_usage()
        return 2
    args = parser.parse_args(argv)
    if args.command == "check":
        return _run_check(args.path)
    if args.command == "docs":
        return _run_docs(check=args.check)
    return 0


def _console_main() -> None:
    sys.exit(main())
