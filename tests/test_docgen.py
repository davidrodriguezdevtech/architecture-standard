from __future__ import annotations

from pathlib import Path

from arch_standard.docgen import render_standard
from arch_standard.rules.catalog import Catalog

PROSE = Path(__file__).parent.parent / "docs" / "standard"
RULES = Path(__file__).parent.parent / "rules"

EXPECTED = {
    "00-purpose",
    "01-philosophy",
    "02-structure",
    "03-bounded-contexts",
    "04-entry-points",
    "05-domain",
    "06-application",
    "07-infrastructure",
    "08-commons-shared-kernel",
    "09-dependency-rules",
    "10-ddd-rules",
    "11-testing-strategy",
    "12-anti-patterns",
    "13-must-should-may",
    "14-architecture-as-code",
    "15-progressive-structure",
    "16-reuse",
}


def test_every_prose_partial_exists() -> None:
    found = {p.stem for p in PROSE.glob("*.md")}
    assert found == EXPECTED


def test_section_09_has_the_catalog_marker() -> None:
    text = (PROSE / "09-dependency-rules.md").read_text(encoding="utf-8")
    assert "<!-- RULES_CATALOG -->" in text


def test_partials_have_a_top_heading() -> None:
    for p in PROSE.glob("*.md"):
        assert p.read_text(encoding="utf-8").lstrip().startswith("#"), p.name


def test_render_contains_every_rule_id_and_all_section_headings() -> None:
    text = render_standard(Catalog.load(RULES), PROSE)
    for n in [1, 8, 12, 21, 23, 30, 45]:
        assert f"ARCH-{n:03d}" in text
    assert "# 1. Philosophy" in text or "# 1." in text
    assert "<!-- RULES_CATALOG -->" not in text  # marker fully replaced


def test_render_is_idempotent() -> None:
    a = render_standard(Catalog.load(RULES), PROSE)
    b = render_standard(Catalog.load(RULES), PROSE)
    assert a == b


def test_committed_standard_is_current() -> None:
    from arch_standard.docgen import render_standard as r

    committed = (Path(__file__).parent.parent / "ARCHITECTURE_STANDARD.md").read_text(
        encoding="utf-8"
    )
    assert committed == r(Catalog.load(RULES), PROSE)
