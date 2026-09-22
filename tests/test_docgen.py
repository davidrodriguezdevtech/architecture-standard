from __future__ import annotations

from pathlib import Path

from arch_standard.docgen import render_standard
from arch_standard.rules.catalog import Catalog, packaged_rules_dir

PROSE = Path(__file__).parent.parent / "docs" / "standard"
RULES = packaged_rules_dir()

EXPECTED = {
    "00-purpose",
    "01-philosophy",
    "02-structure",
    "03-bounded-contexts",
    "04-entry-points",
    "05-domain",
    "06-application",
    "07-adapters",
    "08-commons",
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


def test_given_the_catalog__when_rendered__then_the_core_table_comes_first() -> None:
    text = render_standard(Catalog.load(RULES), PROSE)
    assert "### Core rules" in text
    assert text.index("### Core rules") < text.index("### dependencies")
    for rid in ("ARCH-046", "ARCH-050", "ARCH-051", "ARCH-052", "ARCH-053"):
        assert rid in text


def test_given_a_rule_block__when_rendered__then_the_tier_is_shown() -> None:
    text = render_standard(Catalog.load(RULES), PROSE)
    assert "**Tier:**" in text


def test_given_a_rule_block__when_rendered__then_the_validation_tool_is_shown() -> None:
    # `MUST | partial` alone never says which part is proven; every rule
    # block must render its validation.tool so the tool used is visible.
    text = render_standard(Catalog.load(RULES), PROSE)
    assert "- **Validation:** `ast-checker`" in text
    assert "- **Validation:** `import-linter`" in text


def test_given_a_rule_with_a_validation_detail__when_rendered__then_the_caveat_is_shown() -> None:
    # ARCH-008's caveat (Task 6/10 honesty language): the generated document
    # is the one artifact readers actually read, so it must say which half
    # of the contract is machine-checked and which is reviewed at PR time.
    text = render_standard(Catalog.load(RULES), PROSE)
    assert "layered contract (import half)" in text
    assert "fails mypy" in text
    assert "raises TypeError" in text
