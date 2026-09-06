from __future__ import annotations

import tomllib
from pathlib import Path

from arch_standard.checks.base import CheckReport, Finding, Outcome, ProjectLayout, outcome_for
from arch_standard.rules.catalog import Catalog

_MANIFEST = "contexts.toml"


def find_cycle(graph: dict[str, list[str]]) -> list[str] | None:
    WHITE, GREY, BLACK = 0, 1, 2
    colour = dict.fromkeys(graph, WHITE)
    stack: list[str] = []

    def visit(node: str) -> list[str] | None:
        colour[node] = GREY
        stack.append(node)
        for nxt in graph.get(node, []):
            if colour.get(nxt, WHITE) == GREY:
                return stack[stack.index(nxt) :] + [nxt]
            if colour.get(nxt, WHITE) == WHITE:
                found = visit(nxt)
                if found:
                    return found
        stack.pop()
        colour[node] = BLACK
        return None

    for node in sorted(graph):
        if colour[node] == WHITE:
            found = visit(node)
            if found:
                return found
    return None


def _load_manifest(path: Path) -> dict[str, list[str]]:
    raw = tomllib.loads(path.read_text(encoding="utf-8"))
    contexts = raw.get("contexts", {})
    return {name: list(cfg.get("depends_on", [])) for name, cfg in contexts.items()}


class ContextGraphCheck:
    rule_ids: tuple[str, ...] = ("ARCH-050",)

    def run(self, project: ProjectLayout, catalog: Catalog) -> list[CheckReport]:
        manifest = project.root / _MANIFEST
        detected = set(project.contexts)
        if not manifest.exists():
            if len(detected) < 2:
                return [CheckReport(rule_id="ARCH-050", outcome=Outcome.SKIP)]
            f = Finding(
                "ARCH-050",
                _MANIFEST,
                None,
                f"{_MANIFEST} is missing but the project has {len(detected)} contexts",
            )
            return [CheckReport("ARCH-050", outcome_for(catalog.get("ARCH-050").level, True), (f,))]

        try:
            graph = _load_manifest(manifest)
        except (tomllib.TOMLDecodeError, AttributeError, TypeError) as exc:
            # I5: contexts.toml is the one file in the whole system a human
            # hand-authors directly. A TOML syntax error or a wrong-shaped
            # entry (e.g. ``sales = "nope"`` instead of a table) must not
            # crash the entire check run — every other rule still needs to
            # report normally in the same invocation.
            f = Finding(
                "ARCH-050",
                _MANIFEST,
                None,
                f"{_MANIFEST} could not be parsed: {exc}",
            )
            return [CheckReport(rule_id="ARCH-050", outcome=Outcome.FAIL, findings=(f,))]

        findings: list[Finding] = []
        for name in sorted(set(graph) - detected):
            findings.append(
                Finding("ARCH-050", _MANIFEST, None, f"declared context {name!r} does not exist")
            )
        for name in sorted(detected - set(graph)):
            findings.append(
                Finding("ARCH-050", _MANIFEST, None, f"context {name!r} is not declared")
            )
        for name, deps in sorted(graph.items()):
            for dep in deps:
                if dep not in graph:
                    findings.append(
                        Finding(
                            "ARCH-050",
                            _MANIFEST,
                            None,
                            f"{name} depends on undeclared context {dep!r}",
                        )
                    )
        cycle = find_cycle(graph)
        if cycle:
            findings.append(
                Finding(
                    "ARCH-050", _MANIFEST, None, f"context dependency cycle: {' -> '.join(cycle)}"
                )
            )
        return [
            CheckReport(
                rule_id="ARCH-050",
                outcome=outcome_for(catalog.get("ARCH-050").level, bool(findings)),
                findings=tuple(findings),
            )
        ]
