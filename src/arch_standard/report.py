from __future__ import annotations

from dataclasses import dataclass, replace

from arch_standard.checks.adr_waivers import Waiver
from arch_standard.checks.base import Check, CheckReport, Finding, Outcome, ProjectLayout
from arch_standard.rules.catalog import Catalog

# Cap findings printed per rule so a handful of MUST failures aren't buried
# under e.g. dozens of ARCH-040 test-naming findings.
_MAX_FINDINGS_PER_RULE = 10


@dataclass(frozen=True)
class Report:
    reports: tuple[CheckReport, ...]

    @classmethod
    def collect(cls, project: ProjectLayout, catalog: Catalog, checks: list[Check]) -> Report:
        if not project.is_scannable():
            reason = (
                "no src/ directory"
                if not project.src.is_dir()
                else "no bounded contexts detected under src/"
            )
            return cls(
                reports=tuple(
                    CheckReport(
                        rule_id=rule.id,
                        outcome=Outcome.ERROR,
                        findings=(
                            Finding(
                                rule_id=rule.id,
                                path=str(project.root),
                                line=None,
                                message=f"nothing to validate: {reason}",
                            ),
                        ),
                    )
                    for rule in catalog
                )
            )
        out: list[CheckReport] = []
        for check in checks:
            out.extend(check.run(project, catalog))
        claimed = {r.rule_id for r in out}
        for rule in catalog:
            if rule.id in claimed:
                continue
            # A rule no check claims is either honestly prose-only, or a
            # machine-backed rule whose check was never built. The second case
            # is a validator defect and must never look like a project result.
            outcome = Outcome.NOT_AUTOMATED if rule.validation.tool == "review" else Outcome.ERROR
            findings = (
                ()
                if outcome is Outcome.NOT_AUTOMATED
                else (
                    Finding(
                        rule_id=rule.id,
                        path=str(project.src),
                        line=None,
                        message=(
                            f"{rule.id} declares validation.tool="
                            f"{rule.validation.tool!r} but no check implements it"
                        ),
                    ),
                )
            )
            out.append(CheckReport(rule_id=rule.id, outcome=outcome, findings=findings))
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
            if report.outcome is Outcome.ERROR:
                return 1
            if report.outcome is Outcome.FAIL and report.rule_id in must:
                return 1
        return 0

    def only(self, rule_ids: set[str]) -> Report:
        return Report(reports=tuple(r for r in self.reports if r.rule_id in rule_ids))

    def format_text(self, catalog: Catalog, header: str | None = None) -> str:
        lines: list[str] = []
        if header is not None:
            lines.append(header)
            lines.append("")
        counts = {o: 0 for o in Outcome}
        for report in sorted(self.reports, key=lambda r: r.rule_id):
            counts[report.outcome] += 1
            try:
                name = catalog.get(report.rule_id).name
            except KeyError:
                name = ""
            lines.append(f"{report.rule_id}  {report.outcome.value:<5} {name}")
            shown, rest = (
                report.findings[:_MAX_FINDINGS_PER_RULE],
                report.findings[_MAX_FINDINGS_PER_RULE:],
            )
            for finding in shown:
                loc = f"{finding.path}:{finding.line}" if finding.line is not None else finding.path
                lines.append(f"    {loc}  {finding.message}")
            if rest:
                lines.append(f"    ... and {len(rest)} more")
        lines.append("")
        lines.append(
            f"{counts[Outcome.PASS]} passed, {counts[Outcome.FAIL]} failed, "
            f"{counts[Outcome.WARN]} warnings, {counts[Outcome.SKIP]} skipped, "
            f"{counts[Outcome.NOT_AUTOMATED]} not automated, "
            f"{counts[Outcome.ERROR]} errored"
        )
        return "\n".join(lines)
