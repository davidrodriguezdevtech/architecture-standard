# Changelog

All notable changes to the Architecture Standard's rule catalog are recorded here,
one version per section. The compatibility policy (spec Section 16.3) governs
what kind of change requires which version bump; `arch-standard release-check`
enforces it in CI on every push and pull request, `arch-standard changelog`
renders these entries.

## 0.2.0

**Breaking: the `infrastructure` layer is renamed `adapters`.** The per-module layer
`<context>/<module>/infrastructure/` is now `<context>/<module>/adapters/`, and the shared
package `commons.infrastructure` (`arch-commons`) is now `commons.adapters`. `entrypoints/`
is unchanged: it remains the context's inbound adapters, and `adapters/` holds the outbound
ones. No rule ID and no `level` changed; every rule that named the layer had its wording and
examples updated. The validator recognizes only the new name (no alias). `arch-commons` is
released as 0.2.0 alongside, since its import path changed.

### Changed

- Every rule whose text or examples named the layer: wording/examples updated (the exact
  count is in the `release-check` line below).
- The copier template generates `adapters/` and imports `commons.adapters`.
- `arch-standard check` now reports an aggregate module still holding an
  `infrastructure/` directory as an ARCH-048 failure, with the rename in the message, so a
  half-migrated project exits non-zero instead of passing silently (the old name made the
  whole outbound layer invisible to the layer contracts). This is detection, not an alias:
  the layering contracts still name only `adapters`.

Classified **minor** per spec Section 16.3, which versions the *rule catalog* and nothing
else: it counts rule-content changes, and no rule `id` or `level` moved here. The break this
release is named for — the project layout and the `commons` import path — is not something
that policy versions, which is why a breaking release still classifies as a minor catalog
bump. `uv run arch-standard release-check --version 0.2.0` confirms:
`OK  0.1.0 -> 0.2.0 (minor bump, 18 rule change(s))`.

#### Migration notes

For each existing project:

1. `git mv src/<context>/<module>/infrastructure src/<context>/<module>/adapters` for every
   aggregate module.
2. Replace imports: `<context>.<module>.infrastructure` -> `<context>.<module>.adapters`, and
   `commons.infrastructure` -> `commons.adapters` (requires `arch-commons` >= 0.2.0).
3. Re-run `arch-standard check .`. A module still holding an `infrastructure/` directory is
   reported by the structure check as an ARCH-048 failure carrying the rename hint, and the
   run exits non-zero.
4. Steps 1-3 only cover code. Grep the whole repository for `infrastructure` and update the
   non-code references too: docs and ADRs, CI config, coverage/per-path thresholds, and any
   checked-in `.importlinter`. Re-render the static contracts with
   `uv run arch-standard render-importlinter .`, then re-run `uv run arch-standard check .`.

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
