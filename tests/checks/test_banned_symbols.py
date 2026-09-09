from __future__ import annotations

from pathlib import Path

from arch_standard.checks.banned_symbols import BannedSymbolsCheck
from arch_standard.checks.base import CheckReport, Outcome, ProjectLayout
from arch_standard.rules.catalog import Catalog, packaged_rules_dir

FIX = Path(__file__).parent.parent / "fixtures"
RULES = packaged_rules_dir()


def _reports(name: str) -> dict[str, CheckReport]:
    layout = ProjectLayout.detect(FIX / name)
    return {r.rule_id: r for r in BannedSymbolsCheck().run(layout, Catalog.load(RULES))}


def test_good_project_clean() -> None:
    reports = _reports("good_project")
    assert all(r.outcome is Outcome.PASS for r in reports.values())


def test_bad_project_flags_framework_import() -> None:
    r = _reports("bad_project")["ARCH-003"]
    assert r.outcome is Outcome.FAIL
    assert any("sqlalchemy" in f.message for f in r.findings)


def test_bad_project_flags_datetime_now() -> None:
    r = _reports("bad_project")["ARCH-004"]
    assert r.outcome is Outcome.FAIL
    assert any("datetime.now" in f.message for f in r.findings)


def test_bad_project_flags_orm_base() -> None:
    r = _reports("bad_project")["ARCH-028"]
    assert r.outcome is Outcome.FAIL


def test_given_a_logging_domain_module__when_checked__then_arch_053_fails() -> None:
    r = _reports("bad_project")["ARCH-053"]
    assert r.outcome is Outcome.FAIL
    assert any("logging" in f.message for f in r.findings)


def test_given_the_modular_fixture__when_checked__then_all_banned_symbol_rules_pass() -> None:
    layout = ProjectLayout.detect(FIX / "modular_project")
    reports = {r.rule_id: r for r in BannedSymbolsCheck().run(layout, Catalog.load(RULES))}
    assert all(r.outcome is Outcome.PASS for r in reports.values()), [
        (rid, [f.message for f in r.findings])
        for rid, r in reports.items()
        if r.outcome is not Outcome.PASS
    ]
