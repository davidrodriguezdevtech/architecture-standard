from __future__ import annotations

from pathlib import Path

import pytest

from arch_standard.rules.catalog import Catalog, CatalogError
from arch_standard.rules.model import Level

FIX = Path(__file__).parent.parent / "fixtures"


def test_load_reads_all_rules() -> None:
    cat = Catalog.load(FIX / "rules_ok")
    assert len(cat) == 3
    assert [r.id for r in cat] == ["ARCH-001", "ARCH-021", "ARCH-033"]


def test_get_by_id() -> None:
    cat = Catalog.load(FIX / "rules_ok")
    assert cat.get("ARCH-021").level is Level.MUST_CONDITIONAL
    with pytest.raises(KeyError):
        cat.get("ARCH-999")


def test_musts_include_conditional() -> None:
    cat = Catalog.load(FIX / "rules_ok")
    assert {r.id for r in cat.musts()} == {"ARCH-001", "ARCH-021", "ARCH-033"}


def test_by_category_groups() -> None:
    cat = Catalog.load(FIX / "rules_ok")
    groups = cat.by_category()
    assert list(groups) == ["dependencies", "model_integrity"]
    assert [r.id for r in groups["model_integrity"]] == ["ARCH-021", "ARCH-033"]


def test_duplicate_id_raises() -> None:
    with pytest.raises(CatalogError, match="ARCH-001"):
        Catalog.load(FIX / "rules_dup")


def test_dangling_related_raises(tmp_path: Path) -> None:
    (tmp_path / "x.yaml").write_text(
        "rules:\n"
        "  - {id: ARCH-050, name: X, level: MAY, automation: manual, category: c,\n"
        "     description: d, rationale: r, correct: y, incorrect: n,\n"
        "     validation: {tool: review}, related: [ARCH-777]}\n"
    )
    with pytest.raises(CatalogError, match="ARCH-777"):
        Catalog.load(tmp_path)
