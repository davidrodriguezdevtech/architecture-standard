from __future__ import annotations

from typing import Any

import pytest
from pydantic import ValidationError

from arch_standard.rules.model import Automation, Level, Rule, Tier, ValidationSpec


def _valid_kwargs() -> dict[str, Any]:
    return dict(
        id="ARCH-001",
        name="Domain independent of infrastructure",
        level=Level.MUST,
        automation=Automation.FULL,
        category="dependencies",
        description="The domain layer does not import the infrastructure layer.",
        rationale="Keeps the core testable and swappable.",
        correct="from sales.domain.model.ports import OrderRepository",
        incorrect="from sales.infrastructure.postgres import PgOrderRepo",
        validation=ValidationSpec(tool="import-linter"),
    )


def test_valid_rule_parses() -> None:
    rule = Rule(**_valid_kwargs())
    assert rule.id == "ARCH-001"
    assert rule.level is Level.MUST


def test_conditional_must_level() -> None:
    assert Level("MUST*") is Level.MUST_CONDITIONAL


def test_bad_id_rejected() -> None:
    with pytest.raises(ValidationError):
        Rule(**{**_valid_kwargs(), "id": "ARCH-1"})


def test_blank_rationale_rejected() -> None:
    with pytest.raises(ValidationError):
        Rule(**{**_valid_kwargs(), "rationale": "   "})


def test_related_must_be_rule_ids() -> None:
    with pytest.raises(ValidationError):
        Rule(**{**_valid_kwargs(), "related": ["nope"]})


def test_rule_is_frozen() -> None:
    rule = Rule(**_valid_kwargs())
    with pytest.raises(ValidationError):
        rule.name = "changed"


def test_given_no_tier__when_parsing_a_rule__then_defaults_to_full() -> None:
    rule = Rule(**_valid_kwargs())
    assert rule.tier is Tier.FULL


def test_given_core_tier__when_parsing_a_rule__then_tier_is_core() -> None:
    rule = Rule(**{**_valid_kwargs(), "tier": "core"})
    assert rule.tier is Tier.CORE
