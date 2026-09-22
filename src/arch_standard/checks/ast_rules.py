from __future__ import annotations

import ast
import re as _re
from collections.abc import Callable
from pathlib import Path

from arch_standard.checks.base import (
    CheckReport,
    Finding,
    Outcome,
    ProjectLayout,
    iter_python_files,
    outcome_for,
)
from arch_standard.rules.catalog import Catalog

_IRREGULAR_PAST = {"Sent", "Paid", "Built", "Made", "Lost", "Found", "Left", "Held", "Set", "Put"}
_MUTABLE_CONTAINERS = {"list", "set", "dict", "List", "Set", "Dict"}
_GWT_RE = _re.compile(r"^test_given_.+__when_.+__then_.+$")
_RESERVED_MODEL_FILES = frozenset(
    {"__init__", "value_objects", "events", "ports", "exceptions", "projections"}
)


def _is_frozen_dataclass(node: ast.ClassDef) -> bool:
    for deco in node.decorator_list:
        call = deco if isinstance(deco, ast.Call) else None
        name = call.func if call else deco
        # ``@dataclass`` is an ast.Name; the qualified ``@dataclasses.dataclass``
        # form is an ast.Attribute — both must be recognized (C2).
        ident = (
            name.id
            if isinstance(name, ast.Name)
            else name.attr
            if isinstance(name, ast.Attribute)
            else None
        )
        if ident == "dataclass":
            if not call:
                return False
            return any(
                kw.arg == "frozen" and isinstance(kw.value, ast.Constant) and kw.value.value is True
                for kw in call.keywords
            )
    return False


def _classes(path: Path) -> list[ast.ClassDef]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    return [n for n in ast.walk(tree) if isinstance(n, ast.ClassDef)]


def _looks_past_tense(name: str) -> bool:
    return name.endswith(("ed", "en")) or name in _IRREGULAR_PAST


def _annotation_root(node: ast.expr | None) -> str | None:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Subscript):
        return _annotation_root(node.value)
    return None


def _aggregate_files(model_dir: Path) -> list[Path]:
    if not model_dir.is_dir():
        return []
    return sorted(p for p in model_dir.glob("*.py") if p.stem not in _RESERVED_MODEL_FILES)


def _check_domain_events(project: ProjectLayout) -> list[Finding]:
    findings: list[Finding] = []
    event_files: list[Path] = []
    for context, module in project.iter_modules():
        event_files.append(project.module_domain_dir(context, module) / "model" / "events.py")
    for events_file in event_files:
        if not events_file.exists():
            continue
        rel = str(events_file.relative_to(project.root))
        for cls in _classes(events_file):
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
    vo_files: list[Path] = []
    for context, module in project.iter_modules():
        vo_files.append(project.module_domain_dir(context, module) / "model" / "value_objects.py")
    for vo_file in vo_files:
        if not vo_file.exists():
            continue
        rel = str(vo_file.relative_to(project.root))
        for cls in _classes(vo_file):
            if not _is_frozen_dataclass(cls):
                findings.append(
                    Finding("ARCH-031", rel, cls.lineno, f"{cls.name} value object is not frozen")
                )
    return findings


def _check_encapsulation_in_file(agg_file: Path, rel: str) -> list[Finding]:
    findings: list[Finding] = []
    for cls in _classes(agg_file):
        for stmt in cls.body:
            if isinstance(stmt, ast.AnnAssign) and isinstance(stmt.target, ast.Name):
                name = stmt.target.id
                root = _annotation_root(stmt.annotation)
                if not name.startswith("_") and root in _MUTABLE_CONTAINERS:
                    findings.append(
                        Finding(
                            "ARCH-019",
                            rel,
                            stmt.lineno,
                            f"{cls.name}.{name} exposes a mutable collection",
                        )
                    )
            if isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef)):
                for deco in stmt.decorator_list:
                    if (
                        isinstance(deco, ast.Attribute)
                        and deco.attr == "setter"
                        and not stmt.name.startswith("_")
                    ):
                        findings.append(
                            Finding(
                                "ARCH-018",
                                rel,
                                stmt.lineno,
                                f"{cls.name}.{stmt.name} has a public setter",
                            )
                        )
    return findings


def _check_aggregate_encapsulation(project: ProjectLayout) -> list[Finding]:
    findings: list[Finding] = []
    for context, module in project.iter_modules():
        model_dir = project.module_domain_dir(context, module) / "model"
        for agg_file in _aggregate_files(model_dir):
            rel = str(agg_file.relative_to(project.root))
            findings.extend(_check_encapsulation_in_file(agg_file, rel))
    return findings


def _check_one_aggregate_per_module(project: ProjectLayout) -> list[Finding]:
    findings: list[Finding] = []
    for context, module in project.iter_modules():
        model_dir = project.module_domain_dir(context, module) / "model"
        files = _aggregate_files(model_dir)
        rel = f"src/{context}/{module}/domain/model"
        if len(files) == 0:
            findings.append(Finding("ARCH-049", rel, None, f"{module} declares no aggregate root"))
        elif len(files) > 1:
            names = ", ".join(f.name for f in files)
            findings.append(
                Finding(
                    "ARCH-049", rel, None, f"{module} declares more than one aggregate: {names}"
                )
            )
        elif files[0].stem != "aggregate":
            findings.append(
                Finding(
                    "ARCH-049",
                    rel,
                    None,
                    f"{module}'s aggregate root is {files[0].name}, expected aggregate.py",
                )
            )
    return findings


def _check_service_size_in_dir(project: ProjectLayout, app_dir: Path) -> list[Finding]:
    findings: list[Finding] = []
    for path in iter_python_files(app_dir):
        rel = str(path.relative_to(project.root))
        for cls in _classes(path):
            if not cls.name.endswith("Service"):
                continue
            methods = [
                n
                for n in cls.body
                if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
                and not n.name.startswith("_")
            ]
            if len(methods) > 7:
                findings.append(
                    Finding(
                        "ARCH-030",
                        rel,
                        cls.lineno,
                        f"{cls.name} has {len(methods)} public methods (> 7)",
                    )
                )
            span = (cls.end_lineno or cls.lineno) - cls.lineno
            if span > 200:
                findings.append(
                    Finding("ARCH-030", rel, cls.lineno, f"{cls.name} spans {span} lines (> 200)")
                )
            init = next(
                (
                    n
                    for n in cls.body
                    if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
                    and n.name == "__init__"
                ),
                None,
            )
            if init and len(init.args.args) - 1 > 5:
                param_count = len(init.args.args) - 1
                findings.append(
                    Finding(
                        "ARCH-030",
                        rel,
                        init.lineno,
                        f"{cls.name}.__init__ has {param_count} params (> 5)",
                    )
                )
    return findings


def _check_service_size(project: ProjectLayout) -> list[Finding]:
    findings: list[Finding] = []
    for context, module in project.iter_modules():
        app_dir = project.module_application_dir(context, module)
        findings.extend(_check_service_size_in_dir(project, app_dir))
    return findings


def _check_test_naming(project: ProjectLayout) -> list[Finding]:
    findings: list[Finding] = []
    tests_dir = project.root / "tests"
    if not tests_dir.exists():
        return findings
    skip_fixtures = "fixtures" not in project.root.parts
    for path in iter_python_files(tests_dir):
        if skip_fixtures and "fixtures" in path.parts:
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if (
                isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
                and node.name.startswith("test_")
                and not _GWT_RE.match(node.name)
            ):
                findings.append(
                    Finding(
                        "ARCH-040",
                        str(path.relative_to(project.root)),
                        node.lineno,
                        f"{node.name} is not given/when/then",
                    )
                )
    return findings


def _check_promotion_thresholds(project: ProjectLayout) -> list[Finding]:
    findings: list[Finding] = []
    for context, module in project.iter_modules():
        model_dir = project.module_domain_dir(context, module) / "model"
        for agg_file in _aggregate_files(model_dir):
            n = len(agg_file.read_text(encoding="utf-8").splitlines())
            if n > 400:
                findings.append(
                    Finding(
                        "ARCH-041",
                        str(agg_file.relative_to(project.root)),
                        None,
                        f"{agg_file.name} is {n} lines (> 400): promote to a package",
                    )
                )
        mod_ports = model_dir / "ports.py"
        if mod_ports.exists() and len(_classes(mod_ports)) > 8:
            findings.append(
                Finding(
                    "ARCH-041",
                    str(mod_ports.relative_to(project.root)),
                    None,
                    "ports.py has > 8 protocols: split into a ports/ package",
                )
            )
    return findings


_WITH_NODES = (ast.With, ast.AsyncWith)
_SCOPE_BOUNDARY_NODES = (ast.FunctionDef, ast.AsyncFunctionDef)


def _names_bound_by_target(target: ast.expr) -> list[str]:
    """Names bound by a ``with ... as TARGET`` target, including tuple/list targets."""
    if isinstance(target, ast.Name):
        return [target.id]
    if isinstance(target, (ast.Tuple, ast.List)):
        return [name for elt in target.elts for name in _names_bound_by_target(elt)]
    return []


def _bindings_opened_by(with_node: ast.With | ast.AsyncWith) -> tuple[set[str], set[str]]:
    """Names and no-``as`` context expressions a ``with`` opens for its own body."""
    names: set[str] = set()
    exprs: set[str] = set()
    for item in with_node.items:
        if item.optional_vars is not None:
            names.update(_names_bound_by_target(item.optional_vars))
        elif isinstance(item.context_expr, (ast.Name, ast.Attribute)):
            exprs.add(ast.unparse(item.context_expr))
    return names, exprs


def _scan_for_uncontained_commits(
    node: ast.AST,
    bound_names: frozenset[str],
    bound_exprs: frozenset[str],
    rel: str,
    scope_name: str,
    findings: list[Finding],
) -> None:
    """Walk ``node``, flagging every ``.commit()`` not lexically inside a matching ``with``.

    ``bound_names``/``bound_exprs`` are the bindings open *at this exact
    point in the tree* -- containment, not "some ``with`` exists somewhere
    in this scope". They are extended only for the recursive calls that
    descend into that ``with``'s own body; a sibling statement after the
    block closes, or a statement in an unrelated branch (e.g. a dead
    ``if False:``), is scanned with the unextended set and so cannot see a
    binding that isn't lexically enclosing it. A nested ``def``/``async
    def`` is its own scope and is skipped entirely here -- the caller
    visits it independently with a fresh, empty binding set, so a binding
    never leaks out of it and a call inside it is never double-counted. A
    ``lambda`` is deliberately NOT a boundary: its body is a single
    expression that can never contain a ``with``, so descending into it
    only ever looks up bindings an *enclosing* ``with`` already
    established.
    """
    if isinstance(node, _SCOPE_BOUNDARY_NODES):
        return
    if isinstance(node, _WITH_NODES):
        for item in node.items:
            _scan_for_uncontained_commits(
                item.context_expr, bound_names, bound_exprs, rel, scope_name, findings
            )
            if item.optional_vars is not None:
                _scan_for_uncontained_commits(
                    item.optional_vars, bound_names, bound_exprs, rel, scope_name, findings
                )
        new_names, new_exprs = _bindings_opened_by(node)
        inner_names = bound_names | new_names
        inner_exprs = bound_exprs | new_exprs
        for stmt in node.body:
            _scan_for_uncontained_commits(stmt, inner_names, inner_exprs, rel, scope_name, findings)
        return
    if (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "commit"
    ):
        receiver = node.func.value
        bound = (isinstance(receiver, ast.Name) and receiver.id in bound_names) or (
            isinstance(receiver, (ast.Name, ast.Attribute)) and ast.unparse(receiver) in bound_exprs
        )
        if not bound:
            findings.append(
                Finding(
                    "ARCH-033",
                    rel,
                    node.lineno,
                    f"{scope_name} commits outside a Unit of Work block; "
                    "open `with self._uow as uow:` and commit through uow",
                )
            )
    for child in ast.iter_child_nodes(node):
        _scan_for_uncontained_commits(child, bound_names, bound_exprs, rel, scope_name, findings)


def _check_unit_of_work_commit(project: ProjectLayout) -> list[Finding]:
    """Flag a ``.commit()`` call that is not lexically contained by a matching ``with``.

    This proves exactly one syntactic property: is every ``.commit()``
    call, at its exact position in the tree, inside the body of a ``with``
    or ``async with`` whose bound name (or, when there is no ``as``, whose
    context-manager expression, verbatim: ``with self._uow:
    self._uow.commit()``) matches the call's receiver -- including
    tuple/list ``as`` targets (``with x as (a, b):``). A commit after the
    block has closed, or reachable only through a branch that does not
    lexically contain the block (e.g. a dead ``if False:``), is NOT
    covered and is flagged like any other unbound commit. A nested
    ``def``/``async def`` is analyzed as its own unit, not as part of its
    parent; a ``lambda`` has no scope of its own and is analyzed as part
    of its enclosing scope, since its body cannot contain a ``with``.
    Module-level and class-body statements are scanned too (labelled
    "module-level code" in findings), not just function bodies. It does
    NOT and cannot decide "does this method change state" -- that is a
    semantic question the AST has no way to answer, so no attempt is made
    to guess it from method names, verbs, or repository access. A method
    that mutates state and never calls ``.commit()`` at all is not caught
    by this check; that is a known, deliberate false-negative, not an
    oversight.
    """
    findings: list[Finding] = []
    for context, module in project.iter_modules():
        app_dir = project.module_application_dir(context, module)
        if not app_dir.is_dir():
            continue
        for path in iter_python_files(app_dir):
            rel = str(path.relative_to(project.root))
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            # Module-level and class-body code: skips every FunctionDef /
            # AsyncFunctionDef it meets (they're handled below, fresh).
            _scan_for_uncontained_commits(
                tree, frozenset(), frozenset(), rel, "module-level code", findings
            )
            for func in (
                n for n in ast.walk(tree) if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
            ):
                # Start from func's own children (body, decorators, defaults)
                # rather than func itself, since func matches the
                # scope-boundary check and would otherwise be skipped outright.
                for child in ast.iter_child_nodes(func):
                    _scan_for_uncontained_commits(
                        child, frozenset(), frozenset(), rel, func.name, findings
                    )
    return findings


_IMPLEMENTED: dict[str, Callable[[ProjectLayout], list[Finding]]] = {
    "ARCH-018": _check_aggregate_encapsulation,
    "ARCH-019": _check_aggregate_encapsulation,
    "ARCH-023": _check_domain_events,
    "ARCH-030": _check_service_size,
    "ARCH-031": _check_value_objects,
    "ARCH-033": _check_unit_of_work_commit,
    "ARCH-040": _check_test_naming,
    "ARCH-041": _check_promotion_thresholds,
    "ARCH-049": _check_one_aggregate_per_module,
}


class AstRulesCheck:
    rule_ids: tuple[str, ...] = (
        "ARCH-018",
        "ARCH-019",
        "ARCH-023",
        "ARCH-030",
        "ARCH-031",
        "ARCH-033",
        "ARCH-040",
        "ARCH-041",
        "ARCH-049",
    )

    def run(self, project: ProjectLayout, catalog: Catalog) -> list[CheckReport]:
        if not project.is_scannable():
            return [CheckReport(rule_id=rid, outcome=Outcome.SKIP) for rid in self.rule_ids]
        reports: list[CheckReport] = []
        for rid in self.rule_ids:
            fn = _IMPLEMENTED.get(rid)
            if fn is None:
                reports.append(CheckReport(rule_id=rid, outcome=Outcome.SKIP))
                continue
            findings = tuple(f for f in fn(project) if f.rule_id == rid)
            outcome = outcome_for(catalog.get(rid).level, bool(findings))
            reports.append(CheckReport(rule_id=rid, outcome=outcome, findings=findings))
        return reports
