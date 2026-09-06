from __future__ import annotations

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
_MODULE_LAYERS: tuple[str, ...] = ("infrastructure", "application", "domain")

# The layering rules encoded by the per-module ``layers`` contract.
_MODULE_LAYER_RULES: tuple[str, ...] = ("ARCH-001", "ARCH-002", "ARCH-005")

# Frameworks that must never reach ``commons.types`` (ARCH-035).
_FRAMEWORK_MODULES: tuple[str, ...] = ("sqlalchemy", "fastapi", "pydantic")

_STATUS_RE = re.compile(r"^(?P<name>.+?)\s+(?P<status>KEPT|BROKEN)\s*$")
_RULE_RE = re.compile(r"ARCH-\d+")


def _roots(project: ProjectLayout) -> list[str]:
    """Root packages import-linter should know about: real contexts plus commons/
    bootstrap, but only when those directories actually exist (C1)."""
    return [
        *project.contexts,
        *(d for d in ("commons", "bootstrap") if (project.src / d).is_dir()),
    ]


def _module_contracts(project: ProjectLayout, context: str) -> list[str]:
    """Render the per-module contracts for a context that HAS aggregate modules.

    - One ``layers`` contract per module, covering ARCH-001/002/005 within that
      module's own domain/application/infrastructure (no ``entrypoints`` layer:
      entrypoints sits above all modules, not nested under one).
    - One ``forbidden`` contract (ARCH-006) when the context has an
      ``entrypoints/`` dir: no module's application may import it.
    - One ``forbidden`` contract (ARCH-046) when the context has 2+ modules: no
      module may import another module's application/infrastructure. Source and
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
            for layer in ("application", "infrastructure")
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

        lines += [
            "[importlinter:contract:ARCH-012]",
            "name = ARCH-012 bounded-context independence",
            "type = independence",
            "modules =",
            *(f"    {context}" for context in project.contexts),
            "",
        ]

    domain_app = _domain_application_modules(project)
    if domain_app and (project.src / "commons").is_dir():
        lines += [
            "[importlinter:contract:ARCH-034]",
            "name = ARCH-034 commons.infrastructure isolated from domain and application",
            "type = forbidden",
            "source_modules =",
            *domain_app,
            "forbidden_modules =",
            "    commons.infrastructure",
            "",
        ]

    if (project.src / "commons" / "types").is_dir():
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
        "ARCH-012",
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
