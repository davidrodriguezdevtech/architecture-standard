from __future__ import annotations

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


def test_check_on_good_project_exits_zero(capsys: pytest.CaptureFixture[str]) -> None:
    code = main(["check", str(FIX / "good_project")])
    assert code == 0
    assert "ARCH-001" in capsys.readouterr().out


def test_check_on_bad_project_exits_one() -> None:
    assert main(["check", str(FIX / "bad_project")]) == 1
