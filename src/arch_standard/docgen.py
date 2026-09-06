from __future__ import annotations

from pathlib import Path

from arch_standard.rules.catalog import Catalog
from arch_standard.rules.model import Rule

_MARKER = "<!-- RULES_CATALOG -->"
_PACKAGED_RULES = Path(__file__).resolve().parents[2] / "rules"


def _rule_block(rule: Rule) -> str:
    parts = [
        f"#### {rule.id} — {rule.name}",
        f"- **Level:** {rule.level.value} · **Automation:** {rule.automation.value} "
        f"· **Category:** {rule.category}",
        f"- **Description:** {rule.description.strip()}",
        f"- **Rationale:** {rule.rationale.strip()}",
        "- **Correct:**",
        "  ```",
        *(f"  {line}" for line in rule.correct.strip().splitlines()),
        "  ```",
        "- **Incorrect:**",
        "  ```",
        *(f"  {line}" for line in rule.incorrect.strip().splitlines()),
        "  ```",
    ]
    if rule.related:
        parts.append(f"- **Related:** {', '.join(rule.related)}")
    return "\n".join(parts)


def _catalog_markdown(catalog: Catalog) -> str:
    out: list[str] = []
    for category, rules in catalog.by_category().items():
        out.append(f"### {category}")
        out.append("")
        out.append("| ID | Rule | Level | Automation |")
        out.append("|---|---|---|---|")
        for r in rules:
            out.append(f"| {r.id} | {r.name} | {r.level.value} | {r.automation.value} |")
        out.append("")
    out.append("### Rule reference")
    out.append("")
    for rule in catalog:
        out.append(_rule_block(rule))
        out.append("")
    return "\n".join(out).rstrip()


def render_standard(catalog: Catalog, prose_dir: Path) -> str:
    partials = sorted(prose_dir.glob("*.md"))
    body = "\n\n---\n\n".join(p.read_text(encoding="utf-8").rstrip() for p in partials)
    return body.replace(_MARKER, _catalog_markdown(catalog)) + "\n"


def write_standard(root: Path) -> Path:
    catalog = Catalog.load(_PACKAGED_RULES)
    text = render_standard(catalog, root / "docs" / "standard")
    target = root / "ARCHITECTURE_STANDARD.md"
    target.write_text(text, encoding="utf-8")
    return target
