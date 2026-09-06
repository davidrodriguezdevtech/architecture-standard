from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from arch_standard.checks.base import CheckReport, Finding, Outcome, ProjectLayout
from arch_standard.rules.catalog import Catalog

# Layer packages, top (least depended-upon) to bottom, within each bounded context.
# ``entrypoints`` is wrapped in parens in the INI so the contract does not error
# when a context omits that layer.
_LAYERED: tuple[str, ...] = ("entrypoints", "infrastructure", "application", "domain")

# The layering rules encoded by the single ``layers`` contract. The v1 mapping is
# coarse: a broken layered contract fails all four (the exact culprit edge is a
# v1.1 refinement, tracked in the plan follow-ups and spec section 17).
_LAYER_RULES: tuple[str, ...] = ("ARCH-001", "ARCH-002", "ARCH-005", "ARCH-006")

# Frameworks that must never reach ``commons.types`` (ARCH-035).
_FRAMEWORK_MODULES: tuple[str, ...] = ("sqlalchemy", "fastapi", "pydantic")

_STATUS_RE = re.compile(r"^(?P<name>.+?)\s+(?P<status>KEPT|BROKEN)\s*$")
_RULE_RE = re.compile(r"ARCH-\d+")


def build_contracts(project: ProjectLayout) -> str:
    """Render an ``.importlinter`` INI for the layering, independence and commons rules."""
    roots = [*project.contexts, "commons", "bootstrap"]
    lines: list[str] = [
        "[importlinter]",
        "root_packages =",
        *(f"    {root}" for root in roots),
        "include_external_packages = True",
        "",
    ]

    if project.contexts:
        lines += [
            "[importlinter:contract:ARCH-001]",
            f"name = {' '.join(_LAYER_RULES)} layered",
            "type = layers",
            "containers =",
            *(f"    {context}" for context in project.contexts),
            "layers =",
            *(f"    ({layer})" if layer == "entrypoints" else f"    {layer}" for layer in _LAYERED),
            "",
            "[importlinter:contract:ARCH-012]",
            "name = ARCH-012 bounded-context independence",
            "type = independence",
            "modules =",
            *(f"    {context}" for context in project.contexts),
            "",
        ]

    domain_app = [
        f"    {context}.{layer}"
        for context in project.contexts
        for layer in ("domain", "application")
        if (project.src / context / layer).is_dir()
    ]
    if domain_app:
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
    )

    def run(self, project: ProjectLayout, catalog: Catalog) -> list[CheckReport]:
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
            )
        finally:
            config_path.unlink(missing_ok=True)

        output = proc.stdout + proc.stderr
        covered, broken = _parse_broken_rules(output)

        if not covered:
            # import-linter could not evaluate any contract (config or import
            # resolution error). Never let that pass silently.
            detail = output.strip() or f"lint-imports exited with {proc.returncode}"
            return [
                CheckReport(
                    rule_id=rule_id,
                    outcome=Outcome.FAIL,
                    findings=(
                        Finding(
                            rule_id=rule_id,
                            path=str(project.src),
                            line=None,
                            message=f"import-linter did not run: {detail}",
                        ),
                    ),
                )
                for rule_id in self.rule_ids
            ]

        reports: list[CheckReport] = []
        for rule_id in self.rule_ids:
            if rule_id in broken:
                reports.append(
                    CheckReport(
                        rule_id=rule_id,
                        outcome=Outcome.FAIL,
                        findings=(
                            Finding(
                                rule_id=rule_id,
                                path=str(project.src),
                                line=None,
                                message="import-linter contract broken",
                            ),
                        ),
                    )
                )
            else:
                reports.append(CheckReport(rule_id=rule_id, outcome=Outcome.PASS))
        return reports
