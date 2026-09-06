from __future__ import annotations

from pathlib import Path

from arch_standard.rules.catalog import Catalog
from arch_standard.rules.model import Automation

RULES_DIR = Path(__file__).parent.parent.parent / "rules"

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
    ]
}


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
