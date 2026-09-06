from __future__ import annotations

from datetime import date
from pathlib import Path

from arch_standard.checks.adr_waivers import Waiver, active_waivers

FIX = Path(__file__).parent.parent / "fixtures" / "adr_ok"


def test_active_waiver_is_returned() -> None:
    waivers = active_waivers(FIX, today=date(2026, 1, 1))
    assert set(waivers) == {"ARCH-021"}
    assert waivers["ARCH-021"][0].scope.startswith("sales")


def test_expired_waiver_is_dropped() -> None:
    waivers = active_waivers(FIX, today=date(2026, 1, 1))
    assert "ARCH-030" not in waivers


def test_no_frontmatter_is_ignored() -> None:
    waivers = active_waivers(FIX, today=date(2026, 1, 1))
    assert all(w.rule_id != "" for ws in waivers.values() for w in ws)


def test_is_active_boundary() -> None:
    w = Waiver(rule_id="ARCH-021", scope="x", expires=date(2026, 6, 1), adr_path="a.md")
    assert w.is_active(date(2026, 6, 1)) is True
    assert w.is_active(date(2026, 6, 2)) is False


def test_missing_dir_returns_empty(tmp_path: Path) -> None:
    assert active_waivers(tmp_path / "nope") == {}
