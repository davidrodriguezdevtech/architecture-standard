from __future__ import annotations

import re
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, field_validator

_ID_RE = re.compile(r"^ARCH-\d{3}$")


class Level(StrEnum):
    MUST = "MUST"
    SHOULD = "SHOULD"
    MAY = "MAY"
    MUST_CONDITIONAL = "MUST*"


class Automation(StrEnum):
    FULL = "full"
    PARTIAL = "partial"
    MANUAL = "manual"


class Tier(StrEnum):
    CORE = "core"
    FULL = "full"


class ValidationSpec(BaseModel):
    model_config = ConfigDict(frozen=True)

    tool: Literal["import-linter", "grimp", "ruff", "ast-checker", "schema", "adr", "review"]
    detail: str | None = None


class Rule(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: str
    name: str
    level: Level
    automation: Automation
    category: str
    description: str
    rationale: str
    correct: str
    incorrect: str
    validation: ValidationSpec
    related: list[str] = []
    tier: Tier = Tier.FULL

    @field_validator("id")
    @classmethod
    def _check_id(cls, value: str) -> str:
        if not _ID_RE.match(value):
            raise ValueError(f"rule id must match ARCH-NNN, got {value!r}")
        return value

    @field_validator("description", "rationale", "correct", "incorrect")
    @classmethod
    def _non_empty(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("field must not be blank")
        return value

    @field_validator("related")
    @classmethod
    def _related_are_ids(cls, value: list[str]) -> list[str]:
        bad = [v for v in value if not _ID_RE.match(v)]
        if bad:
            raise ValueError(f"related entries must be rule ids: {bad}")
        return value
