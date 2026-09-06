from __future__ import annotations

import ast
from pathlib import Path

from arch_standard.checks.base import (
    CheckReport,
    Finding,
    ProjectLayout,
    iter_python_files,
    outcome_for,
)
from arch_standard.rules.catalog import Catalog

_QUERY_PREFIXES = ("find_", "search_", "list_", "report_", "query_")
_COLLECTION_ROOTS = {"list", "List", "Sequence", "Iterable", "tuple", "set"}


def _classes(path: Path) -> list[ast.ClassDef]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    return [n for n in ast.walk(tree) if isinstance(n, ast.ClassDef)]


def _mutates_self(cls: ast.ClassDef) -> bool:
    for node in ast.walk(cls):
        if isinstance(node, ast.FunctionDef) and not node.name.startswith("__"):
            for stmt in ast.walk(node):
                if isinstance(stmt, ast.Assign):
                    for tgt in stmt.targets:
                        if (
                            isinstance(tgt, ast.Attribute)
                            and isinstance(tgt.value, ast.Name)
                            and tgt.value.id == "self"
                        ):
                            return True
    return False


def _check_no_context_application(project: ProjectLayout) -> list[Finding]:
    findings: list[Finding] = []
    for context in project.contexts:
        if not project.modules(context):
            # A legacy, single-aggregate context (domain/application/infrastructure
            # directly under the context, no aggregate-module split yet) is not
            # in the new aggregate-module shape this rule targets: the coordination
            # layer it warns about only exists once a context has split into
            # sibling aggregate modules.
            continue
        path = project.src / context / "application"
        if path.is_dir():
            findings.append(
                Finding(
                    "ARCH-048",
                    str(path.relative_to(project.root)),
                    None,
                    f"{context} has a context-level application/ package",
                )
            )
    return findings


def _check_shared_is_limited(project: ProjectLayout) -> list[Finding]:
    findings: list[Finding] = []
    for context in project.contexts:
        for path in iter_python_files(project.shared_dir(context)):
            rel = str(path.relative_to(project.root))
            for cls in _classes(path):
                if cls.name.endswith(("Service", "Repository")):
                    findings.append(
                        Finding(
                            "ARCH-047", rel, cls.lineno, f"{cls.name} does not belong in shared/"
                        )
                    )
                elif _mutates_self(cls):
                    findings.append(
                        Finding(
                            "ARCH-047",
                            rel,
                            cls.lineno,
                            f"{cls.name} mutates its own state; shared/ holds value objects",
                        )
                    )
    return findings


def _annotation_root(node: ast.expr | None) -> str | None:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Subscript):
        return _annotation_root(node.value)
    return None


def _check_repositories_are_not_queries(project: ProjectLayout) -> list[Finding]:
    findings: list[Finding] = []
    for context, module in project.iter_modules():
        ports = project.module_domain_dir(context, module) / "model" / "ports.py"
        if not ports.exists():
            continue
        rel = str(ports.relative_to(project.root))
        for cls in _classes(ports):
            if not cls.name.endswith("Repository"):
                continue
            for stmt in cls.body:
                if not isinstance(stmt, ast.FunctionDef):
                    continue
                if not stmt.name.startswith(_QUERY_PREFIXES):
                    continue
                if _annotation_root(stmt.returns) in _COLLECTION_ROOTS:
                    findings.append(
                        Finding(
                            "ARCH-051",
                            rel,
                            stmt.lineno,
                            f"{cls.name}.{stmt.name} is a query, not aggregate retrieval; "
                            f"move it to {context}/read/",
                        )
                    )
    return findings


class StructureCheck:
    rule_ids: tuple[str, ...] = ("ARCH-047", "ARCH-048", "ARCH-051")

    def run(self, project: ProjectLayout, catalog: Catalog) -> list[CheckReport]:
        by_rule = {
            "ARCH-047": _check_shared_is_limited(project),
            "ARCH-048": _check_no_context_application(project),
            "ARCH-051": _check_repositories_are_not_queries(project),
        }
        return [
            CheckReport(
                rule_id=rid,
                outcome=outcome_for(catalog.get(rid).level, bool(findings)),
                findings=tuple(findings),
            )
            for rid, findings in by_rule.items()
        ]
