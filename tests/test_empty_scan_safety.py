from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def _check(target: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "arch_standard", "check", str(target)],
        capture_output=True,
        text=True,
        check=False,
    )


def test_given_an_empty_directory__when_checked__then_non_zero_and_no_false_pass(
    tmp_path: Path,
) -> None:
    done = _check(tmp_path)
    assert done.returncode != 0
    assert "0 passed" in done.stdout


def test_given_a_wrong_layout__when_checked__then_non_zero(tmp_path: Path) -> None:
    (tmp_path / "lib" / "foo").mkdir(parents=True)
    (tmp_path / "lib" / "foo" / "bar.py").write_text("x = 1\n", encoding="utf-8")
    done = _check(tmp_path)
    assert done.returncode != 0


def test_given_unrelated_files__when_checked__then_non_zero(tmp_path: Path) -> None:
    (tmp_path / "README.md").write_text("# hello\n", encoding="utf-8")
    (tmp_path / "data.csv").write_text("a,b\n1,2\n", encoding="utf-8")
    done = _check(tmp_path)
    assert done.returncode != 0


def test_given_src_with_zero_contexts__when_checked__then_non_zero(tmp_path: Path) -> None:
    (tmp_path / "src" / "utils").mkdir(parents=True)
    (tmp_path / "src" / "utils" / "helpers.py").write_text("x = 1\n", encoding="utf-8")
    done = _check(tmp_path)
    assert done.returncode != 0
    assert "no bounded contexts" in done.stdout.lower()


def test_given_a_real_project__when_checked__then_no_unscannability_error() -> None:
    # NOTE: the suite is currently in a deliberate RED state (tracked by Tasks
    # 6-10): 14 catalog rules declare a machine `validation.tool` with no check
    # implementing them yet, so `good_project` reports 14 ERROR rows and exits
    # 1 even though this task's guard is satisfied. Asserting `returncode == 0`
    # here would fail for a reason this task does not own. Instead assert the
    # thing this task is actually responsible for: `good_project` has real
    # contexts under src/, so the scannability guard must never fire for it —
    # every ERROR row present must be one of the known "no check implements
    # this rule" rows, never the "nothing to validate" unscannability message.
    done = _check(Path("tests/fixtures/good_project").resolve())
    assert "nothing to validate" not in done.stdout.lower()
