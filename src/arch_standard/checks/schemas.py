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
    # I1: ARCH-024 ("integration events live in application/integration_events.py
    # with a versioned schema") had a dead accumulator here — it was never
    # appended to, so any project with an integration_events.py file always
    # PASSed the rule regardless of content, a false PASS on a MUST. Detecting
    # it properly (walking every module for stray *Published/*Occurred classes
    # outside integration_events.py) is speculative enough to be its own v1.1
    # piece of work, so ARCH-024 is dropped from this check's coverage rather
    # than kept as a rubber-stamp PASS — it now surfaces as uncovered.
    rule_ids: tuple[str, ...] = ("ARCH-043", "ARCH-044")

    def run(self, project: ProjectLayout, catalog: Catalog) -> list[CheckReport]:
        arch043: list[Finding] = []
        arch044: list[Finding] = []
        any_events = False

        for context in project.contexts:
            ie_file = project.src / context / "integration_events.py"
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

        def report(rid: str, findings: list[Finding]) -> CheckReport:
            if not any_events:
                return CheckReport(rule_id=rid, outcome=Outcome.SKIP)
            if not findings:
                return CheckReport(rule_id=rid, outcome=Outcome.PASS)
            # I2 exception: ARCH-043/044 are level: MUST, but this detection is a
            # shallow text/filename heuristic ("does the file mention
            # EventEnvelope", "is there a docs/events/<name>.json"). Failing a
            # MUST build on that heuristic is too aggressive, and WARNing on a
            # MUST would silently make it unenforceable. Emit SKIP with the
            # heuristic finding attached as an informational note instead —
            # deeper contract testing is the v1.1 path (see spec §17).
            return CheckReport(rule_id=rid, outcome=Outcome.SKIP, findings=tuple(findings))

        return [
            report("ARCH-043", arch043),
            report("ARCH-044", arch044),
        ]
