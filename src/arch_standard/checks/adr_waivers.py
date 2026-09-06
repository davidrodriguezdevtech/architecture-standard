from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from pathlib import Path

import yaml


@dataclass(frozen=True)
class Waiver:
    rule_id: str
    scope: str
    expires: date
    adr_path: str

    def is_active(self, today: date) -> bool:
        return self.expires >= today


def _frontmatter(text: str) -> dict[str, object] | None:
    if not text.startswith("---"):
        return None
    end = text.find("\n---", 3)
    if end == -1:
        return None
    block = text[3:end]
    parsed = yaml.safe_load(block)
    return parsed if isinstance(parsed, dict) else None


def active_waivers(adr_dir: Path, today: date | None = None) -> dict[str, list[Waiver]]:
    today = today or date.today()
    out: dict[str, list[Waiver]] = {}
    if not adr_dir.is_dir():
        return out
    for path in sorted(adr_dir.glob("*.md")):
        fm = _frontmatter(path.read_text(encoding="utf-8"))
        if not fm or "waives" not in fm:
            continue
        expires = fm.get("expires")
        if not isinstance(expires, date):
            continue
        waiver = Waiver(
            rule_id=str(fm["waives"]),
            scope=str(fm.get("scope", "")),
            expires=expires,
            adr_path=path.name,
        )
        if waiver.is_active(today):
            out.setdefault(waiver.rule_id, []).append(waiver)
    return out
