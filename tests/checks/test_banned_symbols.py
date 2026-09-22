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


def _domain_file(tmp_path: Path, body: str) -> ProjectLayout:
    """A minimal project with one domain/model file, for isolated ARCH-003 checks."""
    domain_model = tmp_path / "src" / "sales" / "orders" / "domain" / "model"
    domain_model.mkdir(parents=True)
    (domain_model / "value_objects.py").write_text(body, encoding="utf-8")
    (tmp_path / "src" / "sales" / "orders" / "domain" / "__init__.py").write_text(
        "", encoding="utf-8"
    )
    return ProjectLayout.detect(tmp_path)


def test_given_domain_imports_emailstr_by_name__when_checked__then_arch_003_passes(
    tmp_path: Path,
) -> None:
    layout = _domain_file(tmp_path, "from pydantic import EmailStr, TypeAdapter, ValidationError\n")
    report = {r.rule_id: r for r in BannedSymbolsCheck().run(layout, Catalog.load(RULES))}[
        "ARCH-003"
    ]
    assert report.outcome is Outcome.PASS


def test_given_domain_imports_basemodel__when_checked__then_arch_003_fails(
    tmp_path: Path,
) -> None:
    """The allowlist is by name, not by module: BaseModel is still banned."""
    layout = _domain_file(tmp_path, "from pydantic import BaseModel\n")
    report = {r.rule_id: r for r in BannedSymbolsCheck().run(layout, Catalog.load(RULES))}[
        "ARCH-003"
    ]
    assert report.outcome is Outcome.FAIL
    assert any("BaseModel" in f.message for f in report.findings)


def test_given_domain_bare_imports_pydantic__when_checked__then_arch_003_fails(
    tmp_path: Path,
) -> None:
    """`import pydantic` stays banned even though EmailStr is allowed by name --
    the bare form would let code reach BaseModel through the module object."""
    layout = _domain_file(tmp_path, "import pydantic\n")
    report = {r.rule_id: r for r in BannedSymbolsCheck().run(layout, Catalog.load(RULES))}[
        "ARCH-003"
    ]
    assert report.outcome is Outcome.FAIL


def test_given_domain_imports_emailstr_and_basemodel_together__when_checked__then_arch_003_fails(
    tmp_path: Path,
) -> None:
    """One allowed name alongside one banned name on the same import still fails."""
    layout = _domain_file(tmp_path, "from pydantic import BaseModel, EmailStr\n")
    report = {r.rule_id: r for r in BannedSymbolsCheck().run(layout, Catalog.load(RULES))}[
        "ARCH-003"
    ]
    assert report.outcome is Outcome.FAIL
    assert any("BaseModel" in f.message and "EmailStr" not in f.message for f in report.findings)


def test_given_a_framework_import_in_commons_adapters__when_checked__then_arch_003_passes(
    tmp_path: Path,
) -> None:
    """commons/adapters/ (ARCH-047) follows adapters/-layer discipline, not domain
    discipline -- a framework import there is exactly what it is for, unlike the
    rest of commons/, which ARCH-003 holds to the same rule as domain/."""
    adapters = tmp_path / "src" / "commons" / "adapters"
    adapters.mkdir(parents=True)
    (adapters / "unit_of_work.py").write_text(
        "from sqlalchemy.orm import Session\n", encoding="utf-8"
    )
    (tmp_path / "src" / "sales" / "entrypoints").mkdir(parents=True)
    layout = ProjectLayout.detect(tmp_path)
    report = {r.rule_id: r for r in BannedSymbolsCheck().run(layout, Catalog.load(RULES))}[
        "ARCH-003"
    ]
    assert report.outcome is Outcome.PASS


def test_given_a_framework_import_directly_in_commons__when_checked__then_arch_003_still_fails(
    tmp_path: Path,
) -> None:
    """The exemption is narrowly commons/adapters/ -- a framework import directly
    in commons/ (not nested under adapters/) is still held to domain discipline."""
    commons = tmp_path / "src" / "commons"
    commons.mkdir(parents=True)
    (commons / "geo.py").write_text("from sqlalchemy.orm import Session\n", encoding="utf-8")
    (tmp_path / "src" / "sales" / "entrypoints").mkdir(parents=True)
    layout = ProjectLayout.detect(tmp_path)
    report = {r.rule_id: r for r in BannedSymbolsCheck().run(layout, Catalog.load(RULES))}[
        "ARCH-003"
    ]
    assert report.outcome is Outcome.FAIL
