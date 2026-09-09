from __future__ import annotations

import re
from pathlib import Path

from arch_standard.rules.catalog import Catalog, packaged_rules_dir
from arch_standard.rules.model import Automation, Level

RULES_DIR = packaged_rules_dir()

# A context name directly followed by domain/application/infrastructure (no
# aggregate module segment in between) is the pre-aggregate-module flat
# shape the standard no longer uses (spec §17 row P).
FLAT_CONTEXT_PATH = re.compile(r"\b(?:sales|billing)[./](?:domain|application|infrastructure)\b")

# ARCH-048 bans a context-level application/ package; its `incorrect` field
# must show exactly the flat shape it forbids, so it is exempt.
FLAT_CONTEXT_PATH_EXEMPT_IDS = {"ARCH-048"}

# every rule ID the spec §9 defines
EXPECTED_IDS = {
    f"ARCH-{n:03d}"
    for n in [
        1,
        2,
        3,
        4,
        5,
        6,
        7,
        8,
        9,
        10,
        11,
        12,
        13,
        14,
        15,
        16,
        17,
        18,
        19,
        20,
        21,
        22,
        23,
        24,
        25,
        26,
        27,
        28,
        29,
        30,
        31,
        32,
        33,
        34,
        35,
        36,
        37,
        38,
        39,
        40,
        41,
        42,
        43,
        44,
        45,
        46,
        47,
        48,
        49,
        50,
        51,
        52,
        53,
    ]
}

CORE_IDS = {
    "ARCH-001",
    "ARCH-002",
    "ARCH-003",
    "ARCH-005",
    "ARCH-006",
    "ARCH-008",
    "ARCH-012",
    "ARCH-023",
    "ARCH-031",
    "ARCH-033",
    "ARCH-046",
    "ARCH-051",
}
NEW_IDS = {f"ARCH-{n:03d}" for n in range(46, 54)}


def test_catalog_loads_clean() -> None:
    cat = Catalog.load(RULES_DIR)
    assert {r.id for r in cat} == EXPECTED_IDS


def test_no_placeholder_prose() -> None:
    cat = Catalog.load(RULES_DIR)
    banned = ("TODO", "TBD", "FIXME", "lorem", "xxx", "placeholder")
    for rule in cat:
        blob = " ".join([rule.description, rule.rationale, rule.correct, rule.incorrect]).lower()
        assert not any(b in blob for b in banned), rule.id
        assert len(rule.description) > 20, rule.id
        assert len(rule.rationale) > 20, rule.id


def test_examples_present_for_every_rule() -> None:
    cat = Catalog.load(RULES_DIR)
    for rule in cat:
        assert rule.correct.strip() and rule.incorrect.strip(), rule.id


def test_full_automation_rules_have_a_machine_tool() -> None:
    cat = Catalog.load(RULES_DIR)
    for rule in cat:
        if rule.automation is Automation.FULL:
            assert rule.validation.tool != "review", rule.id


def test_given_the_catalog__when_loaded__then_the_new_rules_are_present() -> None:
    cat = Catalog.load(RULES_DIR)
    assert {r.id for r in cat} >= NEW_IDS


def test_given_the_catalog__when_filtering_core__then_exactly_the_twelve() -> None:
    cat = Catalog.load(RULES_DIR)
    assert {r.id for r in cat.core()} == CORE_IDS
    assert len(cat.core()) == 12


def test_given_the_catalog__when_reading_conditional_rules__then_they_are_must_star() -> None:
    cat = Catalog.load(RULES_DIR)
    for rid in ("ARCH-024", "ARCH-043", "ARCH-044"):
        assert cat.get(rid).level is Level.MUST_CONDITIONAL, rid


def test_given_a_core_rule__when_read__then_it_is_machine_checkable() -> None:
    cat = Catalog.load(RULES_DIR)
    for rule in cat.core():
        assert rule.validation.tool != "review", rule.id


def test_given_the_catalog__when_reading_examples__then_no_stale_flat_context_paths() -> None:
    cat = Catalog.load(RULES_DIR)
    for rule in cat:
        if rule.id in FLAT_CONTEXT_PATH_EXEMPT_IDS:
            continue
        for field_name in ("correct", "incorrect"):
            text = getattr(rule, field_name)
            match = FLAT_CONTEXT_PATH.search(text)
            assert match is None, (
                f"{rule.id}.{field_name} still uses a pre-aggregate-module flat path "
                f"({match.group(0) if match else '?'}); insert the aggregate module "
                f"segment, e.g. sales/orders/domain/..."
            )


def test_given_repo_root__when_changelog_exists__then_starts_with_changelog_header() -> None:
    changelog = Path(__file__).resolve().parents[2] / "CHANGELOG.md"
    assert changelog.is_file(), "CHANGELOG.md is missing from the repo root"
    content = changelog.read_text(encoding="utf-8")
    assert content.startswith("# Changelog")
    assert "## 0.1.0" in content
