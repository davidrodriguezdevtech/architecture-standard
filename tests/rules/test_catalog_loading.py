from __future__ import annotations

from pathlib import Path

import pytest

from arch_standard.rules.catalog import Catalog, CatalogError


def test_given_a_missing_rules_dir__when_loading__then_raises(tmp_path: Path) -> None:
    with pytest.raises(CatalogError, match="does not exist"):
        Catalog.load(tmp_path / "nope")


def test_given_an_empty_rules_dir__when_loading__then_raises(tmp_path: Path) -> None:
    (tmp_path / "rules").mkdir()
    with pytest.raises(CatalogError, match="no rule files"):
        Catalog.load(tmp_path / "rules")


def test_given_yaml_with_no_rules__when_loading__then_raises(tmp_path: Path) -> None:
    rules = tmp_path / "rules"
    rules.mkdir()
    (rules / "empty.yaml").write_text("rules: []\n", encoding="utf-8")
    with pytest.raises(CatalogError, match="zero rules"):
        Catalog.load(rules)


def test_given_the_real_catalog__when_loading__then_all_rules_load() -> None:
    """Guards against the strict checks above rejecting the genuine catalog."""
    catalog = Catalog.load(Path("rules").resolve())
    assert len(catalog) == 53
