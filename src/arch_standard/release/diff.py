from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from arch_standard.rules.catalog import Catalog
from arch_standard.rules.model import Level


class ChangeKind(StrEnum):
    ADDED = "added"
    REMOVED = "removed"
    LEVEL_CHANGED = "level_changed"
    CONTENT_CHANGED = "content_changed"


@dataclass(frozen=True)
class RuleChange:
    rule_id: str
    kind: ChangeKind
    old_level: Level | None = None
    new_level: Level | None = None


def diff_catalogs(old: Catalog, new: Catalog) -> list[RuleChange]:
    old_ids = {rule.id for rule in old}
    new_ids = {rule.id for rule in new}
    changes: list[RuleChange] = []

    for rule_id in sorted(new_ids - old_ids):
        new_rule = new.get(rule_id)
        changes.append(RuleChange(rule_id=rule_id, kind=ChangeKind.ADDED, new_level=new_rule.level))

    for rule_id in sorted(old_ids - new_ids):
        old_rule = old.get(rule_id)
        changes.append(
            RuleChange(rule_id=rule_id, kind=ChangeKind.REMOVED, old_level=old_rule.level)
        )

    for rule_id in sorted(old_ids & new_ids):
        old_rule, new_rule = old.get(rule_id), new.get(rule_id)
        if old_rule.level != new_rule.level:
            changes.append(
                RuleChange(
                    rule_id=rule_id,
                    kind=ChangeKind.LEVEL_CHANGED,
                    old_level=old_rule.level,
                    new_level=new_rule.level,
                )
            )
        elif old_rule != new_rule:
            changes.append(
                RuleChange(
                    rule_id=rule_id,
                    kind=ChangeKind.CONTENT_CHANGED,
                    old_level=old_rule.level,
                    new_level=new_rule.level,
                )
            )

    return changes
