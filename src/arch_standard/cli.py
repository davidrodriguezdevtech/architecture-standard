from __future__ import annotations

import argparse
import sys
from importlib.metadata import version as _pkg_version
from pathlib import Path

from arch_standard.checks import all_checks
from arch_standard.checks.adr_waivers import active_waivers
from arch_standard.checks.base import CheckReport, Outcome, ProjectLayout
from arch_standard.docgen import render_standard, write_standard
from arch_standard.report import Report
from arch_standard.rules.catalog import Catalog
from arch_standard.version_stamp import majors_crossed, read_stamp

_PACKAGED_RULES = Path(__file__).resolve().parents[2] / "rules"


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="arch-standard")
    sub = parser.add_subparsers(dest="command")
    check = sub.add_parser("check", help="validate a project against the rule catalog")
    check.add_argument("path", nargs="?", default=".", help="project root (default: cwd)")
    check.add_argument("--core", action="store_true", help="run only the core rule set")
    docs = sub.add_parser("docs", help="render ARCHITECTURE_STANDARD.md from the catalog")
    docs.add_argument("--check", action="store_true", help="fail if the committed doc is stale")
    return parser


def _drift_notice(root: Path) -> str | None:
    stamp = read_stamp(root)
    if stamp is None:
        return None
    running = _pkg_version("arch-standard")
    crossed = majors_crossed(stamp.standard_version, running)
    if not crossed:
        return None
    crossed_str = ", ".join(f"v{m}" for m in crossed)
    return (
        f"NOTICE: project is stamped standard-version={stamp.standard_version}, "
        f"running arch-standard {running} -- crossed major {crossed_str}. "
        "Upgrading the stamp is your decision; this does not fail the build."
    )


def _run_check(path: str, core: bool = False) -> int:
    root = Path(path).resolve()
    layout = ProjectLayout.detect(root)
    rules_dir = root / "rules" if (root / "rules").is_dir() else _PACKAGED_RULES
    catalog = Catalog.load(rules_dir)
    waivers = active_waivers(root / "docs" / "adr")
    report = Report.collect(layout, catalog, all_checks())
    header = None
    if core:
        core_ids = {r.id for r in catalog.core()}
        report = report.only(core_ids)
        # I1: a core rule with no check implementing it yet (ARCH-008,
        # ARCH-033) never appears in Report.collect's output at all. Without
        # this, --core silently shows fewer rows than its own "(N)" header
        # claims. Mark the gap honestly as SKIP instead of omitting it.
        present = {r.rule_id for r in report.reports}
        missing = core_ids - present
        if missing:
            report = Report(
                reports=(
                    *report.reports,
                    *(CheckReport(rule_id=rid, outcome=Outcome.SKIP) for rid in sorted(missing)),
                )
            )
        header = f"core rules only ({len(core_ids)})"
    report = report.with_waivers(waivers)
    print(report.format_text(catalog, header=header))
    notice = _drift_notice(root)
    if notice is not None:
        print(notice)
    return report.exit_code(catalog)


def _run_docs(check: bool) -> int:
    root = Path.cwd()
    if check:
        expected = render_standard(Catalog.load(_PACKAGED_RULES), root / "docs" / "standard")
        current = (root / "ARCHITECTURE_STANDARD.md").read_text(encoding="utf-8")
        if current != expected:
            print("ARCHITECTURE_STANDARD.md is stale — run `arch-standard docs`")
            return 1
        print("ARCHITECTURE_STANDARD.md is current")
        return 0
    path = write_standard(root)
    print(f"wrote {path}")
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
        return _run_check(args.path, core=args.core)
    if args.command == "docs":
        return _run_docs(check=args.check)
    return 0


def _console_main() -> None:
    sys.exit(main())
