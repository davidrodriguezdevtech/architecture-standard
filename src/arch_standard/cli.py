from __future__ import annotations

import argparse
import sys
from importlib.metadata import version as _pkg_version
from pathlib import Path

from arch_standard.checks import all_checks
from arch_standard.checks.adr_waivers import active_waivers
from arch_standard.checks.base import CheckReport, Outcome, ProjectLayout
from arch_standard.checks.import_contracts import build_contracts
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
    release_snapshot = sub.add_parser(
        "release-snapshot", help="freeze the current rules/ catalog as a released version"
    )
    release_snapshot.add_argument("version", help="the version being released, e.g. 1.1.0")
    release_check = sub.add_parser(
        "release-check", help="verify a pending catalog change against the compatibility policy"
    )
    release_check.add_argument("--version", required=True, help="the version being released")
    release_check.add_argument("--rules-dir", default=None, help="rules dir (default: ./rules)")
    changelog = sub.add_parser("changelog", help="render and prepend a CHANGELOG.md entry")
    changelog.add_argument("--version", required=True)
    changelog.add_argument("--rules-dir", default=None)
    changelog.add_argument("--changelog-file", default="CHANGELOG.md")
    changelog.add_argument("--migration-notes", default=None, help="path to a migration-notes file")
    render_importlinter = sub.add_parser(
        "render-importlinter",
        help="write a static .importlinter from the current project structure",
    )
    render_importlinter.add_argument(
        "path", nargs="?", default=".", help="project root (default: cwd)"
    )
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


def _run_release_snapshot(version: str) -> int:
    from arch_standard.release.snapshot import write_snapshot

    dest = write_snapshot(Path.cwd() / "rules", version)
    print(f"wrote snapshot {dest}")
    return 0


def _run_release_check(version: str, rules_dir_arg: str | None) -> int:
    from arch_standard.release.compatibility import (
        actual_bump,
        bump_satisfies,
        find_unsanctioned_must_promotions,
        required_bump,
    )
    from arch_standard.release.diff import diff_catalogs
    from arch_standard.release.snapshot import latest_snapshot_version, snapshot_dir

    rules_dir = Path(rules_dir_arg) if rules_dir_arg else Path.cwd() / "rules"
    previous = latest_snapshot_version(rules_dir)
    if previous is None:
        print(
            "no released snapshot to compare against -- run `arch-standard release-snapshot` first"
        )
        return 1

    old_catalog = Catalog.load(snapshot_dir(rules_dir, previous))
    new_catalog = Catalog.load(rules_dir)
    changes = diff_catalogs(old_catalog, new_catalog)

    violations = find_unsanctioned_must_promotions(changes)
    if violations:
        for rule_id in violations:
            print(f"{rule_id} FAIL  jumps to MUST/MUST* without being SHOULD in {previous}")
        return 1

    required = required_bump(changes)
    actual = actual_bump(previous, version)
    if not bump_satisfies(actual, required):
        print(
            f"FAIL  {previous} -> {version} is a {actual} bump, but this diff "
            f"requires at least a {required} bump"
        )
        return 1

    print(f"OK  {previous} -> {version} ({actual} bump, {len(changes)} rule change(s))")
    return 0


def _run_changelog(
    version: str,
    rules_dir_arg: str | None,
    changelog_file_arg: str,
    migration_notes_arg: str | None,
) -> int:
    from arch_standard.release.changelog import render_changelog_entry
    from arch_standard.release.diff import ChangeKind, diff_catalogs
    from arch_standard.release.snapshot import latest_snapshot_version, snapshot_dir
    from arch_standard.rules.model import Level

    rules_dir = Path(rules_dir_arg) if rules_dir_arg else Path.cwd() / "rules"
    previous = latest_snapshot_version(rules_dir)
    if previous is None:
        print(
            "no released snapshot to compare against -- run `arch-standard release-snapshot` first"
        )
        return 1

    old_catalog = Catalog.load(snapshot_dir(rules_dir, previous))
    new_catalog = Catalog.load(rules_dir)
    changes = diff_catalogs(old_catalog, new_catalog)

    binding = (Level.MUST, Level.MUST_CONDITIONAL)
    # find_unsanctioned_must_promotions is release-check's own gate (sanctioned
    # vs. unsanctioned promotions); changelog only needs to know a MUST
    # promotion happened at all, sanctioned or not, to require migration notes.
    must_promotions = [
        change
        for change in changes
        if change.kind == ChangeKind.LEVEL_CHANGED and change.new_level in binding
    ]

    migration_notes: str | None = None
    if migration_notes_arg:
        migration_notes = Path(migration_notes_arg).read_text(encoding="utf-8").strip()
    elif must_promotions:
        promoted = ", ".join(change.rule_id for change in must_promotions)
        print(f"FAIL  {promoted} newly binding as MUST -- pass --migration-notes")
        return 1

    entry = render_changelog_entry(version, old_catalog, new_catalog, changes, migration_notes)

    changelog_path = Path(changelog_file_arg)
    existing = (
        changelog_path.read_text(encoding="utf-8")
        if changelog_path.is_file()
        else "# Changelog\n\n"
    )
    header, _, rest = existing.partition("\n\n")
    changelog_path.write_text(f"{header}\n\n{entry}\n{rest}", encoding="utf-8")
    print(f"wrote {changelog_path}")
    return 0


def _run_render_importlinter(path: str) -> int:
    root = Path(path).resolve()
    layout = ProjectLayout.detect(root)
    ini = build_contracts(layout)
    (root / ".importlinter").write_text(ini, encoding="utf-8")
    print(f"wrote {root / '.importlinter'}")
    return 0


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    parser = _build_parser()
    if not argv:
        parser.print_help()
        return 0
    if argv[0] not in {
        "check",
        "docs",
        "release-snapshot",
        "release-check",
        "changelog",
        "render-importlinter",
        "-h",
        "--help",
    }:
        parser.print_usage()
        return 2
    args = parser.parse_args(argv)
    if args.command == "check":
        return _run_check(args.path, core=args.core)
    if args.command == "docs":
        return _run_docs(check=args.check)
    if args.command == "release-snapshot":
        return _run_release_snapshot(args.version)
    if args.command == "release-check":
        return _run_release_check(args.version, args.rules_dir)
    if args.command == "changelog":
        return _run_changelog(
            args.version, args.rules_dir, args.changelog_file, args.migration_notes
        )
    if args.command == "render-importlinter":
        return _run_render_importlinter(args.path)
    return 0


def _console_main() -> None:
    sys.exit(main())
