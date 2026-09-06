from __future__ import annotations

from dataclasses import dataclass, replace

from arch_standard.checks.adr_waivers import Waiver
from arch_standard.checks.base import Check, CheckReport, Finding, Outcome, ProjectLayout
from arch_standard.rules.catalog import Catalog


@dataclass(frozen=True)
class Report:
    reports: tuple[CheckReport, ...]

    @classmethod
    def collect(cls, project: ProjectLayout, catalog: Catalog, checks: list[Check]) -> Report:
        out: list[CheckReport] = []
        for check in checks:
            out.extend(check.run(project, catalog))
        return cls(reports=tuple(out))

    def with_waivers(self, waivers: dict[str, list[Waiver]]) -> Report:
        updated: list[CheckReport] = []
        for report in self.reports:
            if report.outcome is Outcome.FAIL and report.rule_id in waivers:
                w = waivers[report.rule_id][0]
                note = Finding(
                    report.rule_id,
                    w.adr_path,
                    None,
                    f"waived by {w.adr_path} until {w.expires.isoformat()}",
                )
                updated.append(
                    replace(
                        report,
                        outcome=Outcome.WARN,
                        findings=(*report.findings, note),
                    )
                )
            else:
                updated.append(report)
        return Report(reports=tuple(updated))

    def exit_code(self, catalog: Catalog) -> int:
        must = {r.id for r in catalog.musts()}
        for report in self.reports:
            if report.outcome is Outcome.FAIL and report.rule_id in must:
                return 1
        return 0

    def format_text(self, catalog: Catalog) -> str:
        lines: list[str] = []
        counts = {o: 0 for o in Outcome}
        for report in sorted(self.reports, key=lambda r: r.rule_id):
            counts[report.outcome] += 1
            try:
                name = catalog.get(report.rule_id).name
            except KeyError:
                name = ""
            lines.append(f"{report.rule_id}  {report.outcome.value:<5} {name}")
            for finding in report.findings:
                loc = f"{finding.path}:{finding.line}" if finding.line is not None else finding.path
                lines.append(f"    {loc}  {finding.message}")
        lines.append("")
        lines.append(
            f"{counts[Outcome.PASS]} passed, {counts[Outcome.FAIL]} failed, "
            f"{counts[Outcome.WARN]} warnings, {counts[Outcome.SKIP]} skipped"
        )
        return "\n".join(lines)
