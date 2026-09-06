from __future__ import annotations

from pathlib import Path

from arch_standard.docgen import render_standard
from arch_standard.rules.catalog import Catalog

ROOT = Path(__file__).parent.parent


def test_packaged_catalog_loads() -> None:
    cat = Catalog.load(ROOT / "rules")
    assert len(cat) >= 45


def test_committed_doc_matches_catalog() -> None:
    text = render_standard(Catalog.load(ROOT / "rules"), ROOT / "docs" / "standard")
    assert (ROOT / "ARCHITECTURE_STANDARD.md").read_text(encoding="utf-8") == text


def test_example_adr_parses() -> None:
    from datetime import date

    from arch_standard.checks.adr_waivers import active_waivers

    waivers = active_waivers(ROOT / "docs" / "adr", today=date(2026, 9, 6))
    assert "ARCH-021" in waivers
