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

DEFAULT_BANNED_IMPORTS = frozenset(
    {
        "sqlalchemy",
        "fastapi",
        "pydantic",
        "requests",
        "httpx",
        "boto3",
        "django",
        "flask",
        "kafka",
        "redis",
    }
)
DEFAULT_BANNED_CALLS = frozenset(
    {
        "datetime.now",
        "datetime.utcnow",
        "uuid.uuid1",
        "uuid.uuid4",
        "time.time",
        "random.random",
        "random.randint",
        "open",
    }
)
# I3: "Base" and "Model" are common hand-rolled domain base-class names too —
# flagging them by bare name false-positives ARCH-028 (a MUST) on compliant
# domain code. Narrowed to the one name that unambiguously means "ORM base".
_ORM_BASES = {"DeclarativeBase"}
DEFAULT_BANNED_LOGGING = frozenset({"logging", "structlog", "loguru"})
_LOG_METHODS = frozenset({"debug", "info", "warning", "warn", "error", "exception", "critical"})


def _dotted(node: ast.expr) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return f"{_dotted(node.value)}.{node.attr}"
    return ""


def _domain_files(project: ProjectLayout) -> list[Path]:
    files: list[Path] = []
    for context, module in project.iter_modules():
        files.extend(iter_python_files(project.module_domain_dir(context, module)))
    for context in project.contexts:
        files.extend(iter_python_files(project.shared_dir(context)))
        # legacy single-level layout, removed in Task 10
        files.extend(iter_python_files(project.domain_dir(context)))
    return files


def _core_files(project: ProjectLayout) -> list[Path]:
    files = _domain_files(project)
    for context, module in project.iter_modules():
        files.extend(iter_python_files(project.module_application_dir(context, module)))
    return files


class BannedSymbolsCheck:
    rule_ids: tuple[str, ...] = ("ARCH-003", "ARCH-004", "ARCH-028", "ARCH-053")

    def run(self, project: ProjectLayout, catalog: Catalog) -> list[CheckReport]:
        imports: list[Finding] = []
        calls: list[Finding] = []
        orm: list[Finding] = []
        logging_findings: list[Finding] = []
        for path in _domain_files(project):
            rel = str(path.relative_to(project.root))
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        top = alias.name.split(".")[0]
                        if top in DEFAULT_BANNED_IMPORTS:
                            imports.append(
                                Finding(
                                    "ARCH-003", rel, node.lineno, f"domain imports {alias.name}"
                                )
                            )
                elif isinstance(node, ast.ImportFrom) and node.module:
                    top = node.module.split(".")[0]
                    if top in DEFAULT_BANNED_IMPORTS:
                        imports.append(
                            Finding("ARCH-003", rel, node.lineno, f"domain imports {node.module}")
                        )
                elif isinstance(node, ast.Call):
                    target = _dotted(node.func)
                    tail = ".".join(target.split(".")[-2:]) if "." in target else target
                    if target in DEFAULT_BANNED_CALLS or tail in DEFAULT_BANNED_CALLS:
                        calls.append(
                            Finding("ARCH-004", rel, node.lineno, f"domain calls {target or tail}")
                        )
                elif isinstance(node, ast.ClassDef):  # noqa: SIM102
                    if any(
                        (isinstance(b, ast.Name) and b.id in _ORM_BASES)
                        or (isinstance(b, ast.Attribute) and b.attr in _ORM_BASES)
                        for b in node.bases
                    ):
                        orm.append(
                            Finding(
                                "ARCH-028",
                                rel,
                                node.lineno,
                                f"{node.name} inherits an ORM base in the domain",
                            )
                        )

        for path in _core_files(project):
            rel = str(path.relative_to(project.root))
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        if alias.name.split(".")[0] in DEFAULT_BANNED_LOGGING:
                            logging_findings.append(
                                Finding("ARCH-053", rel, node.lineno, f"core imports {alias.name}")
                            )
                elif isinstance(node, ast.ImportFrom) and node.module:
                    if node.module.split(".")[0] in DEFAULT_BANNED_LOGGING:
                        logging_findings.append(
                            Finding("ARCH-053", rel, node.lineno, f"core imports {node.module}")
                        )
                elif isinstance(node, ast.Call):
                    target = _dotted(node.func)
                    head, _, method = target.rpartition(".")
                    if method in _LOG_METHODS and "log" in head.lower():
                        logging_findings.append(
                            Finding("ARCH-053", rel, node.lineno, f"core logs via {target}")
                        )

        def report(rid: str, findings: list[Finding]) -> CheckReport:
            return CheckReport(
                rule_id=rid,
                outcome=outcome_for(catalog.get(rid).level, bool(findings)),
                findings=tuple(findings),
            )

        return [
            report("ARCH-003", imports),
            report("ARCH-004", calls),
            report("ARCH-028", orm),
            report("ARCH-053", logging_findings),
        ]
