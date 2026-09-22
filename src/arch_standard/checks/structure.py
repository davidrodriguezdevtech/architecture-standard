from __future__ import annotations

import ast
import re
from pathlib import Path

from arch_standard.checks.ast_rules import _aggregate_files
from arch_standard.checks.base import (
    CheckReport,
    Finding,
    Outcome,
    ProjectLayout,
    iter_python_files,
    outcome_for,
)
from arch_standard.rules.catalog import Catalog

_QUERY_PREFIXES = ("find_", "search_", "list_", "report_", "query_")
_COLLECTION_ROOTS = {"list", "List", "Sequence", "Iterable", "tuple", "set"}

# The outbound-adapter layer's pre-0.2.0 directory name. It is NOT an accepted
# alias: nothing in the validator treats it as a layer (the layering contracts
# name only `adapters`). It is recognised here solely so that a project still
# using it is told to rename, instead of having its whole outbound layer
# silently vanish from every contract -- which is what happened before, and
# what made the 0.2.0 migration note's "the validator reports it" untrue.
_LEGACY_ADAPTERS_DIR = "infrastructure"


def _classes(path: Path) -> list[ast.ClassDef]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    return [n for n in ast.walk(tree) if isinstance(n, ast.ClassDef)]


def _mutates_self(cls: ast.ClassDef) -> bool:
    for node in ast.walk(cls):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and not node.name.startswith(
            "__"
        ):
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


def _check_no_legacy_adapters_layer(project: ProjectLayout) -> list[Finding]:
    """ARCH-048's second half: a layer package under a name the standard dropped.

    ARCH-048 is the catalog's layer-package placement rule -- it says which
    layer packages may exist and where. `<context>/<module>/infrastructure/` is
    one that may not: since 0.2.0 the module's layers are domain/, application/
    and adapters/, and a directory under the old name is a half-migrated
    project, not a compliant one.
    """
    findings: list[Finding] = []
    for context, module in project.iter_modules():
        legacy = project.src / context / module / _LEGACY_ADAPTERS_DIR
        if not legacy.is_dir():
            continue
        findings.append(
            Finding(
                "ARCH-048",
                str(legacy.relative_to(project.root)),
                None,
                f"{context}/{module}/{_LEGACY_ADAPTERS_DIR}/ is the pre-0.2.0 name of the "
                "adapters layer; rename it to adapters/ and update the imports "
                "(see CHANGELOG 0.2.0)",
            )
        )
    return findings


def _check_commons_is_limited(project: ProjectLayout) -> list[Finding]:
    findings: list[Finding] = []
    commons = project.commons_dir()
    services_path = commons / "services.py"
    commons_adapters = project.commons_adapters_dir()
    for path in iter_python_files(commons):
        # commons/adapters/ is the documented home for framework-bound technical
        # adapters shared across contexts (ARCH-047) -- it follows adapters/-layer
        # discipline, not the domain discipline the rest of commons/ is held to, so
        # neither the name-suffix ban nor the no-mutation check applies there.
        if commons_adapters in path.parents:
            continue
        rel = str(path.relative_to(project.root))
        # C2: commons/services.py is the documented home for domain services
        # spanning aggregates, so it is exempt from the *Service name-suffix ban
        # -- but a stateful "service" hiding an aggregate is still wrong there,
        # so the mutation check still applies.
        is_services_file = path == services_path
        for cls in _classes(path):
            if not is_services_file and cls.name.endswith(("Service", "Repository")):
                findings.append(
                    Finding("ARCH-047", rel, cls.lineno, f"{cls.name} does not belong in commons/")
                )
            elif _mutates_self(cls):
                findings.append(
                    Finding(
                        "ARCH-047",
                        rel,
                        cls.lineno,
                        f"{cls.name} mutates its own state; commons/ holds value objects",
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


def _snake(name: str) -> str:
    return re.sub(r"(?<!^)(?=[A-Z])", "_", name).lower()


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
                if not isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef)):
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
                        f"{cls.name}.{stmt.name} is a query, not aggregate retrieval; move it to "
                        f"this module's own Finder (application/{module}_finder.py + "
                        f"adapters/{module}_finder.py), or to {context}/read/ if it spans "
                        "2+ aggregate modules",
                    )
                )
    return findings


def _check_init_files_present(project: ProjectLayout) -> list[Finding]:
    """Every Python package directory under src/ has an __init__.py.

    Directory-name-agnostic on purpose: any directory that (recursively)
    contains a .py file is treated as a package and must have one, whether
    it's a context, an aggregate module, domain/model/, services/, read/, or
    anything else the tree grows. src/ itself is the source root, not a
    package, and is exempt.

    src/commons/ is one inverted case: it is a PEP 420 namespace portion that
    merges with the installed arch-commons distribution, so an __init__.py
    there would shadow commons.types/commons.adapters outright instead of
    merging with them. It is reported when it HAS one. src/commons/adapters/,
    if present, is the second inverted case for the same reason one level
    down: it merges with arch-commons' own commons/adapters/ portion, which
    ships without an __init__.py precisely so a project can contribute its
    own framework-bound adapters alongside it (ARCH-047). Directories nested
    under commons/ otherwise -- including inside commons/adapters/ itself --
    follow the normal rule.
    """
    findings: list[Finding] = []
    src = project.src
    if not src.is_dir():
        return findings
    commons = project.commons_dir()
    commons_adapters = project.commons_adapters_dir()
    for namespace_portion in (commons, commons_adapters):
        init_file = namespace_portion / "__init__.py"
        if init_file.exists():
            findings.append(
                Finding(
                    "ARCH-055",
                    str(init_file.relative_to(project.root)),
                    None,
                    f"{namespace_portion.relative_to(src)}/ is a PEP 420 namespace "
                    "portion and must not have an __init__.py; it would shadow the "
                    "matching portion the installed arch-commons package ships",
                )
            )
    for path in sorted(p for p in src.rglob("*") if p.is_dir()):
        if path.name == "__pycache__" or path.name.startswith("."):
            continue
        if path in (commons, commons_adapters):
            continue
        has_py = any(p.suffix == ".py" for p in path.rglob("*.py") if "__pycache__" not in p.parts)
        if not has_py:
            continue
        if not (path / "__init__.py").exists():
            findings.append(
                Finding(
                    "ARCH-055",
                    str(path.relative_to(project.root)),
                    None,
                    f"{path.relative_to(src)}/ is a Python package directory with no __init__.py",
                )
            )
    return findings


def _check_domain_services_location(project: ProjectLayout) -> list[Finding]:
    findings: list[Finding] = []
    for context, module in project.iter_modules():
        domain_dir = project.module_domain_dir(context, module)
        services_file = domain_dir / "services.py"
        if services_file.exists():
            findings.append(
                Finding(
                    "ARCH-054",
                    str(services_file.relative_to(project.root)),
                    None,
                    f"{module} has a domain/services.py file; use domain/services/ instead"
                    " (one file per service, named after the aggregate when there's only one)",
                )
            )
            continue
        services_dir = domain_dir / "services"
        if not services_dir.is_dir():
            continue
        service_files = sorted(p for p in services_dir.glob("*.py") if p.stem != "__init__")
        if len(service_files) != 1:
            continue
        aggregate_name = _aggregate_class_name(domain_dir / "model")
        if aggregate_name is None:
            continue
        expected = _snake(aggregate_name)
        if service_files[0].stem != expected:
            findings.append(
                Finding(
                    "ARCH-054",
                    str(service_files[0].relative_to(project.root)),
                    None,
                    f"{module}'s only domain service is {service_files[0].name}, expected "
                    f"{expected}.py (named after the aggregate)",
                )
            )
    return findings


def _imported_module(node: ast.AST) -> list[str]:
    """Every dotted module path an import statement references."""
    if isinstance(node, ast.ImportFrom) and node.module:
        return [node.module]
    if isinstance(node, ast.Import):
        return [alias.name for alias in node.names]
    return []


def _check_entrypoint_single_aggregate(project: ProjectLayout) -> list[Finding]:
    """Each entrypoint file serves at most one aggregate module (ARCH-056).

    Only meaningful when a context has 2+ aggregate modules to conflate; a
    single-module context has nothing to check. Detected by which
    ``<context>.<module>.*`` packages a file imports from -- a file touching
    two different modules' packages is doing more than one aggregate's job.
    """
    findings: list[Finding] = []
    for context in project.contexts:
        modules = project.modules(context)
        if len(modules) < 2:
            continue
        entry_root = project.entrypoints_dir(context)
        if not entry_root.is_dir():
            continue
        prefix = f"{context}."
        for path in sorted(entry_root.rglob("*.py")):
            if path.stem == "__init__" or "__pycache__" in path.parts:
                continue
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            touched: set[str] = set()
            for node in ast.walk(tree):
                for dotted in _imported_module(node):
                    if not dotted.startswith(prefix):
                        continue
                    head = dotted[len(prefix) :].split(".")[0]
                    if head in modules:
                        touched.add(head)
            if len(touched) > 1:
                findings.append(
                    Finding(
                        "ARCH-056",
                        str(path.relative_to(project.root)),
                        None,
                        f"imports from {len(touched)} aggregate modules "
                        f"({', '.join(sorted(touched))}); split into one file per module",
                    )
                )
    return findings


def _check_bootstrap_no_adapters(project: ProjectLayout) -> list[Finding]:
    """bootstrap/ wires adapters, it does not define them (ARCH-059).

    A class defined under bootstrap/ that directly subclasses a name imported
    from commons.types or commons.adapters is adapter-shaped code sitting in
    the composition root instead of an adapters/ directory. A base class
    reached by indirection through another project module is not resolved --
    this stays a direct-import check, not a full type-hierarchy walk.
    """
    findings: list[Finding] = []
    bootstrap = project.bootstrap_dir()
    if not bootstrap.is_dir():
        return findings
    for path in sorted(bootstrap.rglob("*.py")):
        if path.stem == "__init__" or "__pycache__" in path.parts:
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        commons_names: set[str] = set()
        for node in ast.walk(tree):
            if (
                isinstance(node, ast.ImportFrom)
                and node.module
                and (
                    node.module in ("commons.types", "commons.adapters")
                    or node.module.startswith(("commons.types.", "commons.adapters."))
                )
            ):
                commons_names.update(alias.asname or alias.name for alias in node.names)
        if not commons_names:
            continue
        rel = str(path.relative_to(project.root))
        for node in ast.walk(tree):
            if not isinstance(node, ast.ClassDef):
                continue
            for base in node.bases:
                name = (
                    base.id
                    if isinstance(base, ast.Name)
                    else base.attr
                    if isinstance(base, ast.Attribute)
                    else None
                )
                if name in commons_names:
                    findings.append(
                        Finding(
                            "ARCH-059",
                            rel,
                            node.lineno,
                            f"{node.name} subclasses {name} (commons.types/commons.adapters) "
                            "in bootstrap/; adapters are wired here, not defined",
                        )
                    )
    return findings


class StructureCheck:
    rule_ids: tuple[str, ...] = (
        "ARCH-047",
        "ARCH-048",
        "ARCH-051",
        "ARCH-054",
        "ARCH-055",
        "ARCH-056",
        "ARCH-059",
    )

    def run(self, project: ProjectLayout, catalog: Catalog) -> list[CheckReport]:
        if not project.is_scannable():
            return [CheckReport(rule_id=rid, outcome=Outcome.SKIP) for rid in self.rule_ids]
        by_rule = {
            "ARCH-047": _check_commons_is_limited(project),
            "ARCH-048": [
                *_check_no_context_application(project),
                *_check_no_legacy_adapters_layer(project),
            ],
            "ARCH-051": _check_repositories_are_not_queries(project),
            "ARCH-059": _check_bootstrap_no_adapters(project),
            "ARCH-054": _check_domain_services_location(project),
            "ARCH-055": _check_init_files_present(project),
            "ARCH-056": _check_entrypoint_single_aggregate(project),
        }
        reports = [
            CheckReport(
                rule_id=rid,
                outcome=outcome_for(catalog.get(rid).level, bool(findings)),
                findings=tuple(findings),
            )
            for rid, findings in by_rule.items()
        ]
        return reports
