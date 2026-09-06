from __future__ import annotations

import ast
from pathlib import Path

from arch_standard.checks.base import (
    CheckReport,
    Finding,
    Outcome,
    ProjectLayout,
)
from arch_standard.rules.catalog import Catalog

_IRREGULAR_PAST = {"Sent", "Paid", "Built", "Made", "Lost", "Found", "Left", "Held", "Set", "Put"}


def _is_frozen_dataclass(node: ast.ClassDef) -> bool:
    for deco in node.decorator_list:
        call = deco if isinstance(deco, ast.Call) else None
        name = call.func if call else deco
        if isinstance(name, ast.Name) and name.id == "dataclass":
            if not call:
                return False
            return any(
                kw.arg == "frozen" and isinstance(kw.value, ast.Constant) and kw.value.value is True
                for kw in call.keywords
            )
    return False


def _has_method(node: ast.ClassDef, method: str) -> bool:
    return any(isinstance(n, ast.FunctionDef) and n.name == method for n in node.body)


def _classes(path: Path) -> list[ast.ClassDef]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    return [n for n in ast.walk(tree) if isinstance(n, ast.ClassDef)]


def _looks_past_tense(name: str) -> bool:
    return name.endswith(("ed", "en")) or name in _IRREGULAR_PAST


def _check_domain_events(project: ProjectLayout) -> list[Finding]:
    findings: list[Finding] = []
    for context in project.contexts:
        events_file = project.domain_dir(context) / "model" / "events.py"
        if not events_file.exists():
            continue
        for cls in _classes(events_file):
            rel = str(events_file.relative_to(project.root))
            if not _is_frozen_dataclass(cls):
                findings.append(
                    Finding("ARCH-023", rel, cls.lineno, f"{cls.name} is not a frozen dataclass")
                )
            if not _looks_past_tense(cls.name):
                findings.append(
                    Finding(
                        "ARCH-023", rel, cls.lineno, f"{cls.name} is not named in the past tense"
                    )
                )
    return findings


def _check_value_objects(project: ProjectLayout) -> list[Finding]:
    findings: list[Finding] = []
    for context in project.contexts:
        vo_file = project.domain_dir(context) / "model" / "value_objects.py"
        if not vo_file.exists():
            continue
        for cls in _classes(vo_file):
            rel = str(vo_file.relative_to(project.root))
            if not _is_frozen_dataclass(cls):
                findings.append(
                    Finding("ARCH-031", rel, cls.lineno, f"{cls.name} value object is not frozen")
                )
    return findings


_IMPLEMENTED: dict[str, object] = {
    "ARCH-023": _check_domain_events,
    "ARCH-031": _check_value_objects,
}


class AstRulesCheck:
    rule_ids = ("ARCH-018", "ARCH-019", "ARCH-023", "ARCH-030", "ARCH-031", "ARCH-040", "ARCH-041")

    def run(self, project: ProjectLayout, catalog: Catalog) -> list[CheckReport]:
        reports: list[CheckReport] = []
        for rid in self.rule_ids:
            fn = _IMPLEMENTED.get(rid)
            if fn is None:
                reports.append(CheckReport(rule_id=rid, outcome=Outcome.SKIP))
                continue
            findings = tuple(fn(project))  # type: ignore[operator]
            outcome = Outcome.FAIL if findings else Outcome.PASS
            reports.append(CheckReport(rule_id=rid, outcome=outcome, findings=findings))
        return reports
