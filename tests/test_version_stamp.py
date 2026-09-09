from __future__ import annotations

from pathlib import Path

import pytest

from arch_standard.version_stamp import (
    StampError,
    VersionStamp,
    majors_crossed,
    parse_semver,
    read_stamp,
)


def test_given_no_stamp_file__when_read__then_returns_none(tmp_path: Path) -> None:
    assert read_stamp(tmp_path) is None


def test_given_stamp_file__when_read__then_returns_versions(tmp_path: Path) -> None:
    (tmp_path / ".arch-standard").write_text(
        'standard-version = "1.0.0"\ntemplate-version = "1.0.0"\n', encoding="utf-8"
    )
    assert read_stamp(tmp_path) == VersionStamp(standard_version="1.0.0", template_version="1.0.0")


def test_given_version_string__when_parsed__then_tuple_of_ints() -> None:
    assert parse_semver("1.2.3") == (1, 2, 3)


def test_given_stamp_ahead_of_or_equal_to_running__when_majors_crossed__then_empty() -> None:
    assert majors_crossed("2.0.0", "2.5.0") == []
    assert majors_crossed("2.0.0", "1.9.0") == []


def test_given_stamp_behind_running_by_two_majors__when_majors_crossed__then_lists_both() -> None:
    assert majors_crossed("0.1.0", "2.3.0") == [1, 2]


def test_given_malformed_toml__when_reading__then_raises_stamp_error(tmp_path: Path) -> None:
    (tmp_path / ".arch-standard").write_text("not toml [[[\n", encoding="utf-8")
    with pytest.raises(StampError, match="not valid TOML"):
        read_stamp(tmp_path)


def test_given_a_missing_key__when_reading__then_raises_naming_the_key(tmp_path: Path) -> None:
    (tmp_path / ".arch-standard").write_text('standard-version = "1.0.0"\n', encoding="utf-8")
    with pytest.raises(StampError, match="template-version"):
        read_stamp(tmp_path)


def test_given_a_non_string_version__when_reading__then_raises(tmp_path: Path) -> None:
    (tmp_path / ".arch-standard").write_text(
        'standard-version = 1\ntemplate-version = "1.0.0"\n', encoding="utf-8"
    )
    with pytest.raises(StampError, match="standard-version"):
        read_stamp(tmp_path)


def test_given_a_malformed_version_string__when_reading__then_raises(tmp_path: Path) -> None:
    (tmp_path / ".arch-standard").write_text(
        'standard-version = "one.two"\ntemplate-version = "1.0.0"\n', encoding="utf-8"
    )
    with pytest.raises(StampError, match="one.two"):
        read_stamp(tmp_path)
