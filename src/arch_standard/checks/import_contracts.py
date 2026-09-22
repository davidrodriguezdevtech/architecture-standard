from __future__ import annotations

import importlib.util
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from arch_standard.checks.base import CheckReport, Finding, Outcome, ProjectLayout, outcome_for
from arch_standard.rules.catalog import Catalog

# Layer packages within a single aggregate module. ``entrypoints`` sits above all
# modules (a context-level sibling, not nested under a module) so it is not part
# of this contract; ARCH-006 (application does not depend on entrypoints) is
# covered separately by a per-context ``forbidden`` contract instead.
_MODULE_LAYERS: tuple[str, ...] = ("adapters", "application", "domain")

# The layering rules encoded by the per-module ``layers`` contract. ARCH-007/008
# ride this same contract, but only partially:
#   - ARCH-007 (application does not construct concrete adapters) is only
#     half covered: this contract (plus ARCH-034) proves application cannot
#     import an adapter class from adapters/ or commons.adapters
#     to construct it, but it does NOT catch a concrete adapter class
#     defined inside application/ itself and instantiated there -- nothing
#     is imported, so no import contract fires; that half is unverified by
#     any machine check and is reviewed at PR time.
#   - ARCH-008 (adapters implement ports; the core imports abstractions
#     only) is only half covered by *this* contract: it proves
#     domain/application import nothing from adapters/, but does not itself
#     verify that a concrete adapter actually inherits the abc.ABC declared
#     in the module's ``ports.py``. That half is not unverified, though --
#     since ports are ``abc.ABC`` with ``@abstractmethod``, an adapter that
#     doesn't inherit fails mypy, and one that inherits but skips a method
#     raises TypeError at instantiation. Neither is an import-linter fact,
#     which is why it isn't proven here.
# There is no separate check for either rule; both ride the same import facts
# ARCH-001/002/005 already enforce.
_MODULE_LAYER_RULES: tuple[str, ...] = (
    "ARCH-001",
    "ARCH-002",
    "ARCH-005",
    "ARCH-007",
    "ARCH-008",
)

# Frameworks that must never reach ``commons.types`` (ARCH-035).
_FRAMEWORK_MODULES: tuple[str, ...] = ("sqlalchemy", "fastapi", "pydantic")

_STATUS_RE = re.compile(r"^(?P<name>.+?)\s+(?P<status>KEPT|BROKEN)\s*$")
_RULE_RE = re.compile(r"ARCH-\d+")


def _importable(name: str) -> bool:
    """``importlib.util.find_spec`` raises ``ModuleNotFoundError`` (rather than
    returning ``None``) when a parent package in a dotted name is absent -- e.g.
    ``find_spec("commons.types")`` when ``commons`` itself is not installed.
    Treat that the same as "not importable"."""
    try:
        return importlib.util.find_spec(name) is not None
    except ModuleNotFoundError:
        return False


def _commons_root_available(project: ProjectLayout) -> bool:
    """True if ``commons`` can be a ``root_packages`` entry: either vendored under
    the project's own src/ (legacy/local-dev layout) or resolvable in the
    interpreter running this check via the installed ``arch-commons`` dependency.

    import-linter's ``ForbiddenContract`` validation unconditionally rejects a
    forbidden target that is a subpackage of a module NOT present in
    ``root_packages`` (e.g. ``commons.adapters`` when ``commons`` itself is
    only an external module) -- this holds regardless of
    ``include_external_packages``. So ``commons`` must be a genuine root package
    for ARCH-034 to validate at all once it is no longer vendored on disk.
    """
    if not project.src.is_dir():
        return False
    if (project.src / "commons").is_dir():
        return True
    return _importable("commons")


def _project_commons_available(project: ProjectLayout) -> bool:
    """True only when the project supplies its OWN ``src/commons/`` portion.

    ``commons`` always resolves to something once arch-commons is installed, so
    the mere importability of ``commons`` says nothing about whether this
    project has transversal modules of its own. ARCH-014 governs the project's
    portion specifically, so its contract is gated on the directory actually
    being present -- absence yields a clean SKIP (I3), never an ERROR or a
    spurious PASS.
    """
    return (project.src / "commons").is_dir()


def _project_commons_modules(project: ProjectLayout) -> list[str]:
    """The project's own ``commons.<module>`` portions, as import-linter modules.

    ``types`` and ``adapters`` are excluded: those are the installed
    arch-commons portions, and ARCH-015's whole point is that they sit BELOW
    the project's own modules rather than beside them.
    """
    root = project.src / "commons"
    if not root.is_dir():
        return []
    names: set[str] = set()
    for path in root.iterdir():
        if path.name.startswith((".", "_")) or path.name in ("types", "adapters"):
            continue
        if path.is_dir():
            names.add(path.name)
        elif path.suffix == ".py":
            names.add(path.stem)
    return [f"    commons.{name}" for name in sorted(names)]


def _roots(project: ProjectLayout) -> list[str]:
    """Root packages import-linter should know about: real contexts plus commons/
    and bootstrap/, but only when those directories actually exist (C1), or
    commons when it resolves via an installed arch-commons instead of being
    vendored."""
    return [
        *project.contexts,
        *(["commons"] if _commons_root_available(project) else []),
        *(["bootstrap"] if (project.src / "bootstrap").is_dir() else []),
    ]


def _module_contracts(project: ProjectLayout, context: str) -> list[str]:
    """Render the per-module contracts for a context that HAS aggregate modules.

    - One ``layers`` contract per module, covering ARCH-001/002/005 within that
      module's own domain/application/adapters (no ``entrypoints`` layer:
      entrypoints sits above all modules, not nested under one).
    - One ``forbidden`` contract (ARCH-006) when the context has an
      ``entrypoints/`` dir: no module's application may import it.
    - One ``forbidden`` contract (ARCH-046) when the context has 2+ modules: no
      module may import another module's application/adapters. Source and
      forbidden modules deliberately overlap for a module's OWN layers (e.g.
      source ``sales.orders`` vs forbidden ``sales.orders.application``) —
      import-linter's ``forbidden`` contract treats overlapping source/forbidden
      pairs (one a subpackage of the other) as not describing a forbiddable
      import and skips them, so a module is never reported as forbidden from
      itself; verified by hand against the real tool (see task report).
    - One ``forbidden`` contract (ARCH-052) when the context has a ``read/`` dir:
      the read side may not import any module's domain/application.
    """
    modules = project.modules(context)
    if not modules:
        return []

    lines: list[str] = []
    for module in modules:
        lines += [
            f"[importlinter:contract:ARCH-layers-{context}-{module}]",
            f"name = {' '.join(_MODULE_LAYER_RULES)} layered ({context}.{module})",
            "type = layers",
            "layers =",
            *(f"    ({context}.{module}.{layer})" for layer in _MODULE_LAYERS),
            "",
        ]

    if project.entrypoints_dir(context).is_dir():
        app_modules = [
            f"    {context}.{module}.application"
            for module in modules
            if project.module_application_dir(context, module).is_dir()
        ]
        if app_modules:
            lines += [
                f"[importlinter:contract:ARCH-006-{context}]",
                f"name = ARCH-006 application does not depend on entrypoints ({context})",
                "type = forbidden",
                "source_modules =",
                *app_modules,
                "forbidden_modules =",
                f"    {context}.entrypoints",
                "",
            ]

    if len(modules) > 1:
        forbidden_046 = [
            f"    {context}.{other}.{layer}"
            for other in modules
            for layer in ("application", "adapters")
            if (project.src / context / other / layer).is_dir()
        ]
        if forbidden_046:
            lines += [
                f"[importlinter:contract:ARCH-046-{context}]",
                f"name = ARCH-046 aggregate module isolation ({context})",
                "type = forbidden",
                "source_modules =",
                *(f"    {context}.{module}" for module in modules),
                "forbidden_modules =",
                *forbidden_046,
                "",
            ]

    if project.read_dir(context).is_dir():
        forbidden_052 = [
            f"    {context}.{module}.{layer}"
            for module in modules
            for layer in ("domain", "application")
            if (project.src / context / module / layer).is_dir()
        ]
        if forbidden_052:
            lines += [
                f"[importlinter:contract:ARCH-052-{context}]",
                f"name = ARCH-052 read layer does not import the write side ({context})",
                "type = forbidden",
                "source_modules =",
                f"    {context}.read",
                "forbidden_modules =",
                *forbidden_052,
                "",
            ]

    return lines


def _domain_application_modules(project: ProjectLayout) -> list[str]:
    """Every existing domain/application package, for ARCH-034's source list.

    Every context now has aggregate modules, so this walks
    ``<ctx>.<mod>.domain`` / ``<ctx>.<mod>.application`` for each module.
    """
    result: list[str] = []
    for context in project.contexts:
        for module in project.modules(context):
            for layer in ("domain", "application"):
                if (project.src / context / module / layer).is_dir():
                    result.append(f"    {context}.{module}.{layer}")
    return result


def _commons_types_importable(project: ProjectLayout) -> bool:
    """ARCH-035's *source* is commons.types itself, so import-linter must be
    able to parse it -- unlike ARCH-034's forbidden *target*, this is not
    covered by include_external_packages. True if commons/types is vendored
    under the project's own src/ (legacy/local-dev layout) or if commons.types
    is installed as the arch-commons dependency in the interpreter running
    this check."""
    if (project.src / "commons" / "types").is_dir():
        return True
    return _importable("commons.types")


def build_contracts(project: ProjectLayout) -> str:
    """Render an ``.importlinter`` INI for the layering, independence and commons rules."""
    roots = _roots(project)
    lines: list[str] = [
        "[importlinter]",
        "root_packages =",
        *(f"    {root}" for root in roots),
        "include_external_packages = True",
        "",
    ]

    if project.contexts:
        # Every context now has aggregate modules, so layering is covered
        # entirely by the per-module contracts from ``_module_contracts``
        # below — ``entrypoints`` is a context-level sibling of the modules,
        # not nested under one, so it cannot share a ``containers``-based
        # layers contract with them.
        for context in project.contexts:
            lines += _module_contracts(project, context)

        # ARCH-013/025 ride this same independence contract, but not equally:
        #   - ARCH-013 (no dependency cycles between contexts) is fully
        #     implied -- zero imports between any pair of contexts strictly
        #     subsumes acyclicity; there is no partial case to caveat.
        #   - ARCH-025 (cross-context communication never by import) is only
        #     half proven: this contract establishes the "never imports"
        #     half, but does NOT verify that a declared contract or ACL
        #     actually exists on the other side -- that half is unverified
        #     by any machine check and is reviewed at PR time.
        lines += [
            "[importlinter:contract:ARCH-012]",
            "name = ARCH-012 ARCH-013 ARCH-025 bounded-context independence",
            "type = independence",
            "modules =",
            *(f"    {context}" for context in project.contexts),
            "",
        ]

    if (project.src / "bootstrap").is_dir() and project.contexts:
        lines += [
            "[importlinter:contract:ARCH-017]",
            "name = ARCH-017 nothing imports bootstrap",
            "type = forbidden",
            "source_modules =",
            *(f"    {context}" for context in project.contexts),
            "forbidden_modules =",
            "    bootstrap",
            "",
        ]

    # ARCH-014's contract only exists when the project has its own src/commons/
    # portion. A project that only consumes the installed arch-commons has
    # nothing of its own to govern here, so its absence must SKIP cleanly (I3),
    # never ERROR or a vacuous PASS -- see ``ImportContractsCheck.run``'s
    # ``covered`` set.
    if _project_commons_available(project) and project.contexts:
        lines += [
            "[importlinter:contract:ARCH-014]",
            "name = ARCH-014 commons imports nothing from any context",
            "type = forbidden",
            "source_modules =",
            "    commons",
            "forbidden_modules =",
            *(f"    {context}" for context in project.contexts),
            "",
        ]

    if _commons_types_importable(project) and project.contexts:
        # ARCH-015: commons.types sits below everything, including the project's
        # own commons.<module> portions -- arch-commons ships independently and
        # cannot see them, so such an import would not resolve in any other project.
        forbidden_015 = [f"    {context}" for context in project.contexts]
        forbidden_015 += _project_commons_modules(project)
        lines += [
            "[importlinter:contract:ARCH-015]",
            "name = ARCH-015 commons.types depends on nothing above it",
            "type = forbidden",
            "source_modules =",
            "    commons.types",
            "forbidden_modules =",
            *forbidden_015,
            "",
        ]

    for context in project.contexts:
        if not project.entrypoints_dir(context).is_dir():
            continue
        # ARCH-009: entrypoints do not import adapters. This is only a
        # partial proof of the rule -- ARCH-009 also requires entrypoints not
        # to *call* persistence/session/HTTP-client code directly, which is a
        # runtime-behaviour fact an import contract cannot see. This contract
        # closes the "does not import" half only.
        outbound = [
            f"    {context}.{module}.adapters"
            for module in project.modules(context)
            if project.module_adapters_dir(context, module).is_dir()
        ]
        if outbound:
            lines += [
                f"[importlinter:contract:ARCH-009-{context}]",
                f"name = ARCH-009 entrypoints do not touch adapters ({context})",
                "type = forbidden",
                "source_modules =",
                f"    {context}.entrypoints",
                "forbidden_modules =",
                *outbound,
                "",
            ]
        # ARCH-011: an entrypoint module may not import a sibling entrypoint.
        # There is no providers.py exemption -- each entrypoint file owns its
        # own wiring getter (ARCH-009), so every file under entrypoints/ is a
        # genuine sibling. Source and forbidden lists deliberately overlap
        # (each sibling appears in both):
        # import-linter skips a source/forbidden pair where one module is the
        # other (or a subpackage of it), so a sibling is never reported as
        # forbidden from itself -- the same property ARCH-046 already relies
        # on (see ``_module_contracts``'s docstring).
        #
        # Recursive (rglob, not glob): entrypoints/ groups by transport kind
        # (web/, events/, crons/, one file per aggregate or per concern), so a
        # sibling can be nested, e.g. entrypoints/web/quote.py. Each file's
        # dotted path relative to entrypoints/ becomes its own "sibling" --
        # this still catches a web/ file importing an events/ file, or two
        # files in the same kind folder importing each other.
        entry_root = project.entrypoints_dir(context)
        siblings = sorted(
            ".".join(p.relative_to(entry_root).with_suffix("").parts)
            for p in entry_root.rglob("*.py")
            if p.stem != "__init__" and "__pycache__" not in p.parts
        )
        if len(siblings) > 1:
            lines += [
                f"[importlinter:contract:ARCH-011-{context}]",
                f"name = ARCH-011 entrypoints do not import each other ({context})",
                "type = forbidden",
                "source_modules =",
                *(f"    {context}.entrypoints.{name}" for name in siblings),
                "forbidden_modules =",
                *(f"    {context}.entrypoints.{name}" for name in siblings),
                "",
            ]

    domain_app = _domain_application_modules(project)
    if domain_app and _commons_root_available(project):
        lines += [
            "[importlinter:contract:ARCH-034]",
            "name = ARCH-034 commons.adapters isolated from domain and application",
            "type = forbidden",
            "source_modules =",
            *domain_app,
            "forbidden_modules =",
            "    commons.adapters",
            "",
        ]

    if _commons_types_importable(project):
        lines += [
            "[importlinter:contract:ARCH-035]",
            "name = ARCH-035 commons.types framework-free",
            "type = forbidden",
            "source_modules =",
            "    commons.types",
            "forbidden_modules =",
            *(f"    {module}" for module in _FRAMEWORK_MODULES),
            "",
        ]

    return "\n".join(lines)


def _lint_imports_argv() -> list[str]:
    """Locate the ``lint-imports`` console script for the running interpreter.

    ``python -m importlinter`` is not runnable in import-linter 2.x, so we invoke
    the console script that ships next to ``sys.executable``. As a last resort we
    drive the click command through ``python -c``.
    """
    scripts_dir = Path(sys.executable).parent
    for name in ("lint-imports.exe", "lint-imports"):
        candidate = scripts_dir / name
        if candidate.is_file():
            return [str(candidate)]
    found = shutil.which("lint-imports")
    if found:
        return [found]
    return [
        sys.executable,
        "-c",
        "from importlinter.cli import lint_imports_command; lint_imports_command()",
    ]


def _parse_broken_rules(output: str) -> tuple[set[str], set[str]]:
    """Return ``(covered_rules, broken_rules)`` parsed from import-linter's report."""
    covered: set[str] = set()
    broken: set[str] = set()
    for line in output.splitlines():
        match = _STATUS_RE.match(line.strip())
        if match is None:
            continue
        rules = set(_RULE_RE.findall(match["name"]))
        if not rules:
            continue
        covered |= rules
        if match["status"] == "BROKEN":
            broken |= rules
    return covered, broken


class ImportContractsCheck:
    rule_ids: tuple[str, ...] = (
        "ARCH-001",
        "ARCH-002",
        "ARCH-005",
        "ARCH-006",
        "ARCH-007",
        "ARCH-008",
        "ARCH-009",
        "ARCH-011",
        "ARCH-012",
        "ARCH-013",
        "ARCH-014",
        "ARCH-015",
        "ARCH-017",
        "ARCH-025",
        "ARCH-034",
        "ARCH-035",
        "ARCH-046",
        "ARCH-052",
    )

    def _fail_all(self, project: ProjectLayout, message: str) -> list[CheckReport]:
        """Map an errored / timed-out import-linter run to FAIL for every covered rule.

        RULING 4: an errored subprocess run must never let a covered rule PASS.
        This always FAILs (it does not go through ``outcome_for``): a tooling
        error is not "this SHOULD-rule was violated", it means the rule could
        not be evaluated at all, which must never look like success. In this
        catalog every rule ImportContractsCheck covers is MUST/MUST*, so the
        result is the same either way.
        """
        return [
            CheckReport(
                rule_id=rule_id,
                outcome=Outcome.FAIL,
                findings=(
                    Finding(
                        rule_id=rule_id,
                        path=str(project.src),
                        line=None,
                        message=message,
                    ),
                ),
            )
            for rule_id in self.rule_ids
        ]

    def run(self, project: ProjectLayout, catalog: Catalog) -> list[CheckReport]:
        if not _roots(project):
            # I5 follow-through: a non-DDD tree (no contexts, no commons/,
            # no bootstrap/) has nothing for import-linter to build a graph
            # from at all — `root_packages =` with nothing under it errors
            # ("build_graph() missing 1 required positional argument"), which
            # _fail_all would turn into a spurious FAIL for every rule. There
            # is nothing to check, so SKIP instead of inventing findings.
            return [CheckReport(rule_id=rid, outcome=Outcome.SKIP) for rid in self.rule_ids]
        ini = build_contracts(project)
        handle, name = tempfile.mkstemp(suffix=".importlinter.ini", text=True)
        os.close(handle)
        config_path = Path(name)
        config_path.write_text(ini, encoding="utf-8")
        try:
            proc = subprocess.run(
                [*_lint_imports_argv(), "--config", str(config_path), "--no-cache"],
                cwd=project.src,
                env={**os.environ, "PYTHONPATH": str(project.src)},
                capture_output=True,
                text=True,
                check=False,
                timeout=120,
            )
        except subprocess.TimeoutExpired:
            return self._fail_all(project, "import-linter timed out after 120s")
        finally:
            config_path.unlink(missing_ok=True)

        output = proc.stdout + proc.stderr
        covered, broken = _parse_broken_rules(output)

        if not covered:
            # No contract was evaluated at all (config or import-resolution error).
            detail = output.strip() or f"lint-imports exited with {proc.returncode}"
            return self._fail_all(project, f"import-linter did not run: {detail}")

        if proc.returncode != 0 and not broken:
            # import-linter errored *after* reporting one or more KEPT contracts
            # (grimp exception, module-not-in-graph, non-zero exit for any reason
            # other than a broken contract). Do not let the un-broken rules PASS.
            detail = output.strip() or "no diagnostic output"
            return self._fail_all(
                project,
                f"import-linter exited {proc.returncode} without reporting a broken "
                f"contract: {detail}",
            )

        reports: list[CheckReport] = []
        for rule_id in self.rule_ids:
            is_broken = rule_id in broken
            findings = (
                (
                    Finding(
                        rule_id=rule_id,
                        path=str(project.src),
                        line=None,
                        message="import-linter contract broken",
                    ),
                )
                if is_broken
                else ()
            )
            # I3: a rule whose contract was never emitted (not in `covered` —
            # e.g. ARCH-046 with only one module, ARCH-052 with no read/ dir,
            # ARCH-006 with no entrypoints/ dir) was never actually evaluated.
            # That is a different category from "checked, no violation found",
            # so it must SKIP rather than report a vacuous PASS.
            outcome = (
                Outcome.SKIP
                if rule_id not in covered
                else outcome_for(catalog.get(rule_id).level, is_broken)
            )
            reports.append(CheckReport(rule_id=rule_id, outcome=outcome, findings=findings))
        return reports
