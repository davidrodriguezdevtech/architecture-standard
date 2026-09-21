from __future__ import annotations

import tomllib
from pathlib import Path

import yaml

from tests.templates.conftest import TEMPLATE_ROOT

REPO_ROOT = Path(__file__).resolve().parents[2]


def _package_version(pyproject_path: Path) -> str:
    with pyproject_path.open("rb") as f:
        data = tomllib.load(f)
    return str(data["project"]["version"])


def _copier_default(field: str) -> str:
    config = yaml.safe_load((TEMPLATE_ROOT / "copier.yml").read_text(encoding="utf-8"))
    return str(config[field]["default"])


def test_given_the_template__when_reading_standard_default__then_it_matches_root_version() -> None:
    # arch-standard and arch-commons are independently versioned (they may
    # legitimately diverge) -- compare each template default only to its own package's
    # pyproject.toml, never to the other default, or a legitimate divergence between
    # the two packages would be misread as drift.
    assert _copier_default("arch_standard_version") == _package_version(
        REPO_ROOT / "pyproject.toml"
    )


def test_given_the_template__when_reading_commons_default__then_matches_commons_version() -> None:
    assert _copier_default("arch_commons_version") == _package_version(
        REPO_ROOT / "packages" / "arch-commons" / "pyproject.toml"
    )
