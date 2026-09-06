from __future__ import annotations

from pathlib import Path

PROSE = Path(__file__).parent.parent / "docs" / "standard"

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
