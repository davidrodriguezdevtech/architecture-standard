from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path
from typing import Any

import yaml

from arch_standard.rules.model import Level, Rule


class CatalogError(Exception):
    pass


class Catalog:
    def __init__(self, rules: list[Rule]) -> None:
        self._rules = sorted(rules, key=lambda r: r.id)
        self._by_id = {r.id: r for r in self._rules}

    @classmethod
    def load(cls, rules_dir: Path) -> Catalog:
        rules: list[Rule] = []
        seen: dict[str, Path] = {}
        for path in sorted(rules_dir.glob("*.yaml")):
            raw: Any = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
            for entry in raw.get("rules", []):
                rule = Rule.model_validate(entry)
                if rule.id in seen:
                    raise CatalogError(
                        f"duplicate rule {rule.id} in {path.name} and {seen[rule.id].name}"
                    )
                seen[rule.id] = path
                rules.append(rule)
        catalog = cls(rules)
        catalog._check_related()
        return catalog

    def _check_related(self) -> None:
        for rule in self._rules:
            for ref in rule.related:
                if ref not in self._by_id:
                    raise CatalogError(f"{rule.id} references unknown rule {ref}")

    def get(self, rule_id: str) -> Rule:
        return self._by_id[rule_id]

    def __iter__(self) -> Iterator[Rule]:
        return iter(self._rules)

    def __len__(self) -> int:
        return len(self._rules)

    def by_category(self) -> dict[str, list[Rule]]:
        groups: dict[str, list[Rule]] = {}
        for rule in self._rules:
            groups.setdefault(rule.category, []).append(rule)
        return groups

    def musts(self) -> list[Rule]:
        return [r for r in self._rules if r.level in (Level.MUST, Level.MUST_CONDITIONAL)]
