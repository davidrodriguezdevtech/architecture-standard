from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path
from typing import Protocol

from arch_standard.rules.catalog import Catalog
from arch_standard.rules.model import Level

_NON_CONTEXT_DIRS = {"commons", "shared_kernel", "bootstrap"}
_SKIP_DIRS = {".venv", "venv", "__pycache__", ".git", ".mypy_cache", ".ruff_cache"}


class Outcome(StrEnum):
    PASS = "PASS"
    FAIL = "FAIL"
    WARN = "WARN"
    SKIP = "SKIP"


def outcome_for(level: Level, has_findings: bool) -> Outcome:
    """Derive an outcome from the catalog's own severity, not a hardcoded rule-ID set.

    MUST / MUST* violations FAIL (they affect the exit code); SHOULD / MAY
    violations WARN. Every check should route its outcome through this helper
    instead of maintaining its own warn/fail rule-ID list.
    """
    if not has_findings:
        return Outcome.PASS
    return Outcome.FAIL if level in (Level.MUST, Level.MUST_CONDITIONAL) else Outcome.WARN


@dataclass(frozen=True)
class Finding:
    rule_id: str
    path: str
    line: int | None
    message: str


@dataclass(frozen=True)
class CheckReport:
    rule_id: str
    outcome: Outcome
    findings: tuple[Finding, ...] = ()


@dataclass(frozen=True)
class ProjectLayout:
    root: Path
    src: Path
    contexts: tuple[str, ...] = field(default=())

    @classmethod
    def detect(cls, root: Path) -> ProjectLayout:
        src = root / "src"
        contexts: tuple[str, ...] = ()
        if src.is_dir():
            contexts = tuple(
                sorted(
                    p.name
                    for p in src.iterdir()
                    if p.is_dir()
                    and p.name not in _NON_CONTEXT_DIRS
                    and not p.name.startswith((".", "_"))
                )
            )
        return cls(root=root, src=src, contexts=contexts)

    def domain_dir(self, context: str) -> Path:
        return self.src / context / "domain"

    def application_dir(self, context: str) -> Path:
        return self.src / context / "application"

    def infrastructure_dir(self, context: str) -> Path:
        return self.src / context / "infrastructure"

    def entrypoints_dir(self, context: str) -> Path:
        return self.src / context / "entrypoints"


class Check(Protocol):
    rule_ids: tuple[str, ...]

    def run(self, project: ProjectLayout, catalog: Catalog) -> list[CheckReport]: ...


def iter_python_files(root: Path) -> Iterator[Path]:
    if not root.exists():
        return
    for path in root.rglob("*.py"):
        if any(part in _SKIP_DIRS for part in path.parts):
            continue
        yield path
