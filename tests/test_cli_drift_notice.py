from __future__ import annotations

from pathlib import Path

import pytest

from arch_standard.cli import main


def test_given_no_stamp__when_check__then_no_drift_notice_printed(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    exit_code = main(["check", str(tmp_path)])
    out = capsys.readouterr().out
    assert exit_code == 0
    assert "NOTICE" not in out


def test_given_stamp_two_majors_behind__when_check__then_notice_names_both_majors(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    (tmp_path / ".arch-standard").write_text(
        'standard-version = "0.1.0"\ntemplate-version = "0.1.0"\n', encoding="utf-8"
    )
    monkeypatch.setattr("arch_standard.cli._pkg_version", lambda _name: "2.3.0")

    exit_code = main(["check", str(tmp_path)])
    out = capsys.readouterr().out

    assert exit_code == 0
    assert "NOTICE" in out
    assert "v1" in out and "v2" in out


def test_given_stamp_current__when_check__then_no_drift_notice(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    (tmp_path / ".arch-standard").write_text(
        'standard-version = "0.1.0"\ntemplate-version = "0.1.0"\n', encoding="utf-8"
    )
    monkeypatch.setattr("arch_standard.cli._pkg_version", lambda _name: "0.1.0")

    exit_code = main(["check", str(tmp_path)])
    out = capsys.readouterr().out

    assert exit_code == 0
    assert "NOTICE" not in out
