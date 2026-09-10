# Changelog

All notable changes to the Architecture Standard's rule catalog are recorded here,
one version per section. The compatibility policy (spec Section 16.3) governs
what kind of change requires which version bump; `arch-standard release-check`
enforces it in CI on every push and pull request, `arch-standard changelog`
renders these entries.

## 0.1.1

Catalog-honesty corrections surfaced by wiring `release-check` into CI (v1 release
hardening, Plan 3.1): seven rules changed `automation` and/or `validation.tool`, none
changed `level`, so no migration notes are required.

### Changed

- ARCH-024, ARCH-042, ARCH-045: `automation: partial -> manual`, `validation.tool:
  schema`/`ast-checker -> review`. Each was advertising machine enforcement that was
  never built; their substance -- intent to consume (024), cross-module usage
  thresholds (042), consumer-driven surface shape (045) -- genuinely requires human
  judgement, not an import/AST fact. This is an honesty correction, not a weakening:
  no rule's `level` changed, and none of the three was actually enforced before.
- ARCH-007, ARCH-008, ARCH-025: `automation: full -> partial`. Each is now enforced by
  attribution to an existing import contract that proves only part of the rule (the
  import-graph half); `validation.detail` names the unverified half that stays a PR
  review item.
- ARCH-009: `validation.tool: ast-checker -> import-linter`, correcting the label to
  match the forbidden-contract that actually implements it.

Classified **patch** per spec Section 16.3 (automation-tier and validation-tool
changes only, no `level` change); `uv run arch-standard release-check --version 0.1.1`
confirms: `OK 0.1.0 -> 0.1.1 (patch bump, 7 rule change(s))`.

## 0.1.0

Initial catalog and tooling: the rule catalog (`rules/*.yaml`), the `arch_standard`
validator package (import-linter contracts, the AST checker, structure and context-graph
checks), `ARCHITECTURE_STANDARD.md` generation, and CI. Includes the aggregate-module
level, the `<context>/read/` layer, the declared context dependency graph, and rule tiers
(12 core rules).
