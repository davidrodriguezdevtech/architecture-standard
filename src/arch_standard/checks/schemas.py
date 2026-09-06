from __future__ import annotations

import ast
import re
from pathlib import Path

from arch_standard.checks.base import CheckReport, Finding, Outcome, ProjectLayout
from arch_standard.rules.catalog import Catalog


def _snake(name: str) -> str:
    return re.sub(r"(?<!^)(?=[A-Z])", "_", name).lower()


def _event_classes(path: Path) -> list[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    return [n.name for n in ast.walk(tree) if isinstance(n, ast.ClassDef)]


class IntegrationEventSchemaCheck:
    rule_ids: tuple[str, ...] = ("ARCH-024", "ARCH-043", "ARCH-044")

    def run(self, project: ProjectLayout, catalog: Catalog) -> list[CheckReport]:
        arch024: list[Finding] = []
        arch043: list[Finding] = []
        arch044: list[Finding] = []
        any_events = False

        for context in project.contexts:
            ie_file = project.application_dir(context) / "integration_events.py"
            if not ie_file.exists():
                continue
            any_events = True
            rel = str(ie_file.relative_to(project.root))
            text = ie_file.read_text(encoding="utf-8")
            if "EventEnvelope" not in text:
                arch043.append(
                    Finding(
                        "ARCH-043",
                        rel,
                        None,
                        f"{context}/integration_events.py does not reference EventEnvelope",
                    )
                )
            for cls_name in _event_classes(ie_file):
                schema_json = project.root / "docs" / "events" / f"{_snake(cls_name)}.json"
                schema_yaml = schema_json.with_suffix(".yaml")
                if not schema_json.exists() and not schema_yaml.exists():
                    arch044.append(
                        Finding("ARCH-044", rel, None, f"no published schema for {cls_name}")
                    )

        def report(rid: str, findings: list[Finding], *, warn: bool) -> CheckReport:
            if not any_events:
                return CheckReport(rule_id=rid, outcome=Outcome.SKIP)
            if not findings:
                return CheckReport(rule_id=rid, outcome=Outcome.PASS)
            return CheckReport(
                rule_id=rid,
                outcome=Outcome.WARN if warn else Outcome.FAIL,
                findings=tuple(findings),
            )

        return [
            report("ARCH-024", arch024, warn=True),
            report("ARCH-043", arch043, warn=True),
            report("ARCH-044", arch044, warn=True),
        ]
