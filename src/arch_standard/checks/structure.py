from __future__ import annotations

import ast
from pathlib import Path

from arch_standard.checks.ast_rules import _aggregate_files
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
        services_path = project.shared_dir(context) / "services.py"
        for path in iter_python_files(project.shared_dir(context)):
            rel = str(path.relative_to(project.root))
            # C2: <context>/shared/services.py is the documented home for domain
            # services spanning aggregates, so it is exempt from the *Service
            # name-suffix ban — but a stateful "service" hiding an aggregate is
            # still wrong there, so the mutation check still applies.
            is_services_file = path == services_path
            for cls in _classes(path):
                if not is_services_file and cls.name.endswith(("Service", "Repository")):
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


def _subscript_element_name(node: ast.expr | None) -> str | None:
    """Resolve the element type name out of a subscripted collection annotation.

    ``list[Order]`` -> ``"Order"``; ``list[some.Order]`` -> ``"Order"``;
    ``list["Order"]`` (a forward-ref string) -> ``"Order"``. Anything else
    (nested generics, unions, ...) resolves to ``None`` and is treated as
    unresolved by the caller (C1: stays conservative in the FAIL direction).
    """
    if not isinstance(node, ast.Subscript):
        return None
    element = node.slice
    if isinstance(element, ast.Name):
        return element.id
    if isinstance(element, ast.Attribute):
        return element.attr
    if isinstance(element, ast.Constant) and isinstance(element.value, str):
        return element.value
    return None


def _aggregate_class_name(model_dir: Path) -> str | None:
    """The module's aggregate type name, if unambiguous (C1).

    Reuses ``ast_rules._aggregate_files`` (the non-reserved files in
    ``domain/model/``) and resolves to a class name only when exactly one
    class is declared across them — matching ARCH-049's "one aggregate per
    module" shape. Anything else (no aggregate file, more than one class —
    e.g. an ARCH-049 violation, or a genuinely ambiguous module) resolves to
    ``None`` so the caller stays conservative in the FAIL direction.
    """
    classes = [cls.name for f in _aggregate_files(model_dir) for cls in _classes(f)]
    return classes[0] if len(classes) == 1 else None


def _check_repositories_are_not_queries(project: ProjectLayout) -> list[Finding]:
    findings: list[Finding] = []
    for context, module in project.iter_modules():
        model_dir = project.module_domain_dir(context, module) / "model"
        ports = model_dir / "ports.py"
        if not ports.exists():
            continue
        rel = str(ports.relative_to(project.root))
        aggregate_name = _aggregate_class_name(model_dir)
        for cls in _classes(ports):
            if not cls.name.endswith("Repository"):
                continue
            for stmt in cls.body:
                if not isinstance(stmt, ast.FunctionDef):
                    continue
                if not stmt.name.startswith(_QUERY_PREFIXES):
                    continue
                if _annotation_root(stmt.returns) not in _COLLECTION_ROOTS:
                    continue
                element = _subscript_element_name(stmt.returns)
                if element is not None and element == aggregate_name:
                    # Returns a collection of the module's own aggregate (e.g.
                    # ``list[Order]`` on ``OrderRepository`` in ``orders``) —
                    # legitimate identity-adjacent retrieval, not a query.
                    continue
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
