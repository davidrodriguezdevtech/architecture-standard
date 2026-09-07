from __future__ import annotations

from arch_standard.release.diff import ChangeKind, RuleChange
from arch_standard.rules.catalog import Catalog


def render_changelog_entry(
    version: str,
    old: Catalog,
    new: Catalog,
    changes: list[RuleChange],
    migration_notes: str | None,
) -> str:
    added = [c for c in changes if c.kind == ChangeKind.ADDED]
    removed = [c for c in changes if c.kind == ChangeKind.REMOVED]
    level_changed = [c for c in changes if c.kind == ChangeKind.LEVEL_CHANGED]
    content_changed = [c for c in changes if c.kind == ChangeKind.CONTENT_CHANGED]

    lines: list[str] = [f"## {version}", ""]

    if added:
        lines.append("### Added")
        for change in added:
            rule = new.get(change.rule_id)
            lines.append(f"- {rule.id} ({rule.level.value}) -- {rule.name}")
        lines.append("")

    if level_changed or content_changed:
        lines.append("### Changed")
        for change in level_changed:
            rule = new.get(change.rule_id)
            old_level = change.old_level.value if change.old_level else "?"
            new_level = change.new_level.value if change.new_level else "?"
            lines.append(f"- {rule.id}: {old_level} -> {new_level} -- {rule.name}")
        for change in content_changed:
            rule = new.get(change.rule_id)
            lines.append(f"- {rule.id}: wording/examples updated -- {rule.name}")
        lines.append("")

    if removed:
        lines.append("### Removed")
        for change in removed:
            rule = old.get(change.rule_id)
            lines.append(f"- {rule.id} -- {rule.name}")
        lines.append("")

    if migration_notes:
        lines.append("#### Migration notes")
        lines.append("")
        lines.append(migration_notes)
        lines.append("")

    return "\n".join(lines)
