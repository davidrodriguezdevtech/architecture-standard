from __future__ import annotations

import re
from pathlib import Path

import pytest

from arch_standard.cli import main

FIX = Path(__file__).parent / "fixtures"


def test_main_with_no_args_prints_usage_and_returns_zero(
    capsys: pytest.CaptureFixture[str],
) -> None:
    code = main([])
    out = capsys.readouterr().out
    assert code == 0
    assert "usage" in out.lower()
    assert "check" in out
    assert "docs" in out


def test_main_with_unknown_subcommand_returns_two(
    capsys: pytest.CaptureFixture[str],
) -> None:
    code = main(["frobnicate"])
    assert code == 2


def test_check_on_good_project_reports_arch_001_and_exits_one_on_unimplemented_checks(
    capsys: pytest.CaptureFixture[str],
) -> None:
    # 14 catalog rules declare a machine tool with no check implementing it
    # yet (Tasks 6-9); Report.collect reports those as ERROR rather than
    # silently omitting them, so even a fully compliant project exits 1
    # until those checks land.
    code = main(["check", str(FIX / "good_project")])
    assert code == 1
    assert "ARCH-001" in capsys.readouterr().out


def test_check_on_bad_project_exits_one() -> None:
    assert main(["check", str(FIX / "bad_project")]) == 1


def test_given_core_mode__when_checking__then_only_core_rules_are_reported(
    capsys: pytest.CaptureFixture[str],
) -> None:
    # ARCH-008 and ARCH-033 are core but declare a machine tool with no check
    # implementing it yet (Tasks 6-9), so Report.collect honestly reports
    # them as ERROR and the run exits 1 until those land.
    assert main(["check", str(FIX / "modular_project"), "--core"]) == 1
    out = capsys.readouterr().out
    assert "core rules only" in out
    assert "ARCH-041" not in out


def test_given_core_mode__when_checking__then_all_12_core_rules_are_shown(
    capsys: pytest.CaptureFixture[str],
) -> None:
    # ARCH-008 and ARCH-033 are tier: core but no check implements them yet;
    # Report.collect guarantees completeness for every catalog rule, so
    # --core still shows exactly the 12 core rows it claims, marking the
    # uncovered two honestly as ERROR (a validator defect) rather than
    # silently omitting them or disguising them as SKIP.
    main(["check", str(FIX / "modular_project"), "--core"])
    out = capsys.readouterr().out
    assert "core rules only (12)" in out
    for rid in (
        "ARCH-001",
        "ARCH-002",
        "ARCH-003",
        "ARCH-005",
        "ARCH-006",
        "ARCH-008",
        "ARCH-012",
        "ARCH-023",
        "ARCH-031",
        "ARCH-033",
        "ARCH-046",
        "ARCH-051",
    ):
        assert rid in out, rid
    assert "ARCH-008  ERROR" in out
    assert "ARCH-033  ERROR" in out
    total = sum(
        int(n)
        for n in re.findall(r"(\d+) (?:passed|failed|warnings|skipped|not automated|errored)", out)
    )
    assert total == 12
