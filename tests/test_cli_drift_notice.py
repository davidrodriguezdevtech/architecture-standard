from __future__ import annotations

import subprocess
import sys
from importlib.metadata import PackageNotFoundError
from pathlib import Path

import pytest

from arch_standard.cli import main


def test_given_no_stamp__when_check__then_no_drift_notice_printed(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    # Any run now exits 1: 14 catalog rules declare a machine tool with no
    # check implementing it yet (Tasks 6-9), so Report.collect reports them
    # as ERROR rather than silently omitting them. This test only cares
    # about drift-notice behavior, not the exit code.
    main(["check", str(tmp_path)])
    out = capsys.readouterr().out
    assert "NOTICE" not in out


def test_given_stamp_two_majors_behind__when_check__then_notice_names_both_majors(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    (tmp_path / ".arch-standard").write_text(
        'standard-version = "0.1.0"\ntemplate-version = "0.1.0"\n', encoding="utf-8"
    )
    monkeypatch.setattr("arch_standard.cli._pkg_version", lambda _name: "2.3.0")

    main(["check", str(tmp_path)])
    out = capsys.readouterr().out

    assert "NOTICE" in out
    assert "v1" in out and "v2" in out


def test_given_stamp_current__when_check__then_no_drift_notice(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    (tmp_path / ".arch-standard").write_text(
        'standard-version = "0.1.0"\ntemplate-version = "0.1.0"\n', encoding="utf-8"
    )
    monkeypatch.setattr("arch_standard.cli._pkg_version", lambda _name: "0.1.0")

    main(["check", str(tmp_path)])
    out = capsys.readouterr().out

    assert "NOTICE" not in out


def test_given_a_broken_stamp__when_checking__then_exit_code_matches_a_clean_run(
    tmp_path: Path,
) -> None:
    """A stamp problem must never look like an architecture violation."""
    import shutil

    good = Path("tests/fixtures/good_project").resolve()
    target = tmp_path / "proj"
    shutil.copytree(good, target)
    clean = subprocess.run(
        [sys.executable, "-m", "arch_standard", "check", str(target)],
        capture_output=True,
        text=True,
        check=False,
    )
    (target / ".arch-standard").write_text("garbage [[[\n", encoding="utf-8")
    broken = subprocess.run(
        [sys.executable, "-m", "arch_standard", "check", str(target)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert broken.returncode == clean.returncode
    assert "Traceback" not in broken.stderr
    assert ".arch-standard" in (broken.stderr + broken.stdout)


def test_given_pkg_version_lookup_fails__when_check__then_warns_and_exit_code_unaffected(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    """importlib.metadata.version() raises PackageNotFoundError when the
    distribution isn't installed (e.g. running straight from a source tree).
    The drift notice is advisory -- this must warn, never crash the run."""
    (tmp_path / ".arch-standard").write_text(
        'standard-version = "0.1.0"\ntemplate-version = "0.1.0"\n', encoding="utf-8"
    )
    baseline_code = main(["check", str(tmp_path)])
    capsys.readouterr()

    def _raise(_name: str) -> str:
        raise PackageNotFoundError("arch-standard")

    monkeypatch.setattr("arch_standard.cli._pkg_version", _raise)
    code = main(["check", str(tmp_path)])
    captured = capsys.readouterr()

    assert code == baseline_code
    assert "Traceback" not in captured.err
    assert "warning" in captured.err.lower()


def test_given_non_semver_running_version__when_check__then_warns_and_exit_code_unaffected(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    """The running arch-standard version can carry a PEP 440 pre-release/dev/
    local tag (e.g. "0.1.0.dev1") that parse_semver's strict N.N.N check
    rejects. That must not escape the advisory drift-notice path either."""
    (tmp_path / ".arch-standard").write_text(
        'standard-version = "0.1.0"\ntemplate-version = "0.1.0"\n', encoding="utf-8"
    )
    baseline_code = main(["check", str(tmp_path)])
    capsys.readouterr()

    monkeypatch.setattr("arch_standard.cli._pkg_version", lambda _name: "0.1.0.dev1")
    code = main(["check", str(tmp_path)])
    captured = capsys.readouterr()

    assert code == baseline_code
    assert "Traceback" not in captured.err
    assert "warning" in captured.err.lower()
