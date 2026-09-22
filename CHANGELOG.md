# Changelog

All notable changes to the Architecture Standard's rule catalog are recorded here,
one version per section. The compatibility policy (spec Section 16.3) governs
what kind of change requires which version bump; `arch-standard release-check`
enforces it in CI on every push and pull request, `arch-standard changelog`
renders these entries.

## 0.3.0

**Added: `tests/` must have the same directory shape as `src/` (ARCH-058, SHOULD).**
A test file whose imports resolve to exactly one `src/` directory now lives at the
mirrored path under `tests/` -- `tests/sales/orders/domain/model/test_aggregate.py`,
not a flattened `tests/test_order_aggregate.py` with the layer folded into the
filename. A test spanning 2+ source directories (a smoke/e2e test through the
composition root) is not flattened by this rule and is left wherever it sits.

### Added
- ARCH-058 (SHOULD) -- a test file's directory mirrors the source it tests

#### Migration notes (tests mirror src)

For each existing project:

1. For every `tests/test_*.py` file that imports from exactly one `src/<context>/
   <module>/<layer>/...` directory, move it to `tests/<context>/<module>/<layer>/
   test_<unit>.py`, adding `__init__.py` files as the rest of the project's test
   tree requires.
2. Leave smoke/e2e tests, `conftest.py`, and shared test infrastructure (builders,
   in-memory doubles, fixtures) where they are -- this rule only places
   `test_*.py` files whose imports point at one source directory.
3. Re-run `uv run arch-standard check .` to confirm ARCH-058 passes.

**Added: a narrow, explicit exception to ARCH-003 for a framework's own scalar
format validators.** Domain (and a project's own `commons/`) MAY import
`pydantic.EmailStr`, `pydantic.TypeAdapter` and `pydantic.ValidationError` by name,
used only to validate one field's string format in `__post_init__`. `import pydantic`
(the bare form) and every other pydantic name -- `BaseModel`, `Field`, decorators --
stay banned. This closes a real gap found in practice: a hand-rolled email regex
duplicated per aggregate, reinventing a problem pydantic already solves correctly,
purely because ARCH-003 read as an all-or-nothing ban.

### Changed
- ARCH-003: reworded to document the allowlist and the line it does not cross
  (scalar TYPE validators, never MODELING machinery). `validation.tool` corrected
  from `import-linter` to `ast-checker`, matching what actually enforces it
  (`BannedSymbolsCheck`) -- the old text was stale, not a behaviour change.

**Clarified: a single-aggregate listing is not a `<context>/read/` concern, and it
is a port -- not a class an entrypoint reaches into `adapters/` for.** Section 2.5's
"what goes where" table listed "search" and "any cross-aggregate read" in the same
row, which reads as license to put a plain paginated listing of one aggregate type
at context level. It is not: `<context>/read/` exists because some queries span
aggregate modules, and a query touching only one aggregate's own data has nothing to
span. That query -- however many rows it returns, however it is filtered, sorted or
paginated -- belongs to that aggregate module's own **Finder**: a `Finder` ABC and
its DTOs in `application/<aggregate>_finder.py` (entrypoint-importable, like any
other application module), implemented in `adapters/<aggregate>_finder.py` (wired by
`bootstrap/`, never imported by an entrypoint directly) -- the same ABC/
implementation split the repository already uses, and for the same reason: ARCH-009
forbids an entrypoint from importing a module's `adapters/` directly. An early
version of this change put the whole Finder in `adapters/`; that breaks ARCH-009 the
moment an entrypoint actually calls it, caught by `lint-imports` before release.

### Changed
- Section 2.5 rewritten around a three-row table (by id / by anything else, same
  aggregate / spanning 2+ aggregates), and gives the Finder's ABC/implementation
  split its own paragraph, mirroring how the repository already splits between
  `domain/model/ports.py` and `adapters/`.
- The canonical tree (2.1) and "what goes where" table (2.3) gained the
  `<aggregate>_finder.py` pair (`application/` + `adapters/`) and the split row.
- ARCH-051: description, rationale and the two-part `correct` example now show the
  Finder as a port (ABC in `application/`, implementation in `adapters/`), with an
  `incorrect` example showing exactly the ARCH-009 violation an unsplit Finder
  causes: an entrypoint importing `adapters/<aggregate>_finder.py` directly.
- ARCH-051's automated finding message (a repository method that looks like a
  query) now names both files of the split, read/ only for a query spanning 2+
  aggregate modules.

No rule `id` was removed and no `level` changed.

#### Migration notes

For each existing project with a `<context>/read/<name>.py` module that only ever
reads one aggregate module's own store:

1. Split it in two: the `Finder` ABC and its query/result DTOs move to that
   aggregate module's `application/<aggregate>_finder.py`; the implementation
   (`InMemoryXFinder` or a real one) moves to `adapters/<aggregate>_finder.py`.
2. Wire the implementation in `bootstrap/`, alongside the repository, and pass the
   `Finder`-typed instance to the entrypoint's `configure()`.
3. Re-run `uv run arch-standard render-importlinter .` and `uv run lint-imports` --
   confirm ARCH-009 stays green (the entrypoint now imports the port from
   `application/`, never the implementation from `adapters/`).
4. Re-run `uv run arch-standard check .` -- ARCH-052's contract is gated on
   `<context>/read/` existing at all, so removing an unneeded `read/` directory
   entirely is safe and causes no new findings.

**Breaking: `<context>/shared/` and `shared_kernel/` are replaced by a single
`src/commons/`.** `commons` becomes a PEP 420 namespace package assembled from two
portions: `commons.types` / `commons.adapters` still ship from the installed
`arch-commons`, and the project supplies its own `commons.<module>` portions from
`src/commons/`. Everything that previously lived above one aggregate -- cross-aggregate
ID types, value objects used by two or more aggregates, domain services spanning
aggregates, and policy-bearing concepts shared across contexts -- now has one home
instead of three. `arch-commons` is released as 0.3.0 alongside, since it drops its
top-level `__init__.py`.

### Changed
- ARCH-014: retargeted -- `shared_kernel imports nothing from any context` becomes
  `commons imports nothing from any context`. Same one-way guarantee, new subject.
- ARCH-015: reworded -- `commons.types` now also imports nothing from the project's own
  `commons.<module>` portions. `arch-commons` ships independently and cannot see them.
- ARCH-016: narrowed -- the "no business logic" ban applies to `commons.types` /
  `commons.adapters` only. A project's own `commons.<module>` MAY carry business
  meaning; that is what it is for.
- ARCH-046: cross-aggregate ID types move from `<context>/shared/ids.py` to
  `commons/ids.py`.
- ARCH-047: retargeted -- `Context shared area is strictly limited` becomes
  `The commons area is strictly limited`. The admission test moves with it, and the
  `services.py` name-suffix carve-out is now `commons/services.py`.
- ARCH-055: gains its one exception -- `src/commons/` MUST NOT have an `__init__.py`,
  because a regular package on either side shadows the other rather than merging.
  Directories nested under it still follow the normal rule.

No `level` changed in this half of the release.

#### Migration notes

For each existing project:

1. Upgrade to `arch-commons` 0.3.0 and delete `src/commons/__init__.py` if one exists.
2. Move `<context>/shared/ids.py` to `src/commons/ids.py`, `<context>/shared/value_objects.py`
   to one `src/commons/<concept>.py` per concept, and `<context>/shared/services.py` to
   `src/commons/services.py`. Delete the now-empty `<context>/shared/` directories.
3. Move anything in `shared_kernel/` to `src/commons/` and delete the directory.
4. Repoint imports: `from <context>.shared.ids import X` becomes `from commons.ids import X`.
5. Add `"src/commons"` to `packages` in `pyproject.toml`, and set `mypy_path = "src"` with
   `explicit_package_bases = true` if not already present -- without them mypy names
   `src/commons/types/` after its own directory and reports it as shadowing the stdlib.
6. Re-run `uv run arch-standard render-importlinter .` -- ARCH-014's contract now names
   `commons`, and ARCH-015's forbidden list now includes the project's own commons modules.
7. Re-run `uv run arch-standard check .`.

**`providers.py` is removed from the standard entirely** -- there is no per-context or
per-module wiring file anymore. ARCH-037 is retired. ARCH-009 and ARCH-011 are reworded
for the replacement pattern, and a new rule, ARCH-057, requires that a web entrypoint
context centralize response shaping (envelopes, error formatting) in one composition-root
mechanism instead of duplicating it per handler. No rule `level` changed in this half
either -- ARCH-057 lands as SHOULD, not MUST, per the "a new MUST never lands directly"
rule (spec Section 16.3).

### Added
- ARCH-057 (SHOULD) -- HTTP entrypoints centralize response shaping in the composition root

### Changed (entrypoints)
- ARCH-005: wording/examples updated -- Application does not depend on adapters
- ARCH-007: wording/examples updated -- Application does not construct concrete adapters
- ARCH-009: wording/examples updated -- Entrypoints obtain wired services from the composition root; never construct or call outbound adapters directly
- ARCH-011: wording/examples updated -- Entrypoints call application services, not other entrypoints

### Removed
- ARCH-037 -- Entrypoint wiring is defined in per-context providers.py, backed by bootstrap

#### Migration notes (entrypoints)

**New pattern.** Each entrypoint file defines its own small getter for the one service it
needs (a `configure()` / `get_x_service()` pair, or the transport's own DI hook), set once
at startup by the composition root (`main.py` -- still the only module allowed to import
`bootstrap/`, ARCH-017). This keeps an aggregate module's wiring self-contained: extracting
it into its own service later needs no untangling of a wiring file shared with other
aggregate modules.

**Why now:** a per-context `providers.py` under `entrypoints/` was also swept into ARCH-009's
"entrypoints do not touch adapters" import-linter contract, which made the standard's own
ARCH-037 example (`providers.py` constructing `SqlAlchemyOrderRepository` directly)
contradict ARCH-009 as written. Moving wiring out of `entrypoints/` and into each
entrypoint file directly (reading from what `main.py` configured) removes the contradiction
and matches how these projects extract into microservices: an aggregate module travels with
its own wiring, not entangled with siblings' construction in one shared file.

**New response-shaping rule (ARCH-057):** a web entrypoint context that wants a uniform
response shape applies it through one composition-root-registered mechanism (e.g. ASGI
middleware wired in `main.py`), never by having each handler build it. The envelope's exact
shape is a project decision this rule does not mandate; only the "one mechanism, one place"
requirement is.

For each existing project:

1. Delete every `<context>/entrypoints/providers.py`.
2. For each entrypoint file that called into it (e.g. `providers.order_service()`),
   replace that with a locally defined `configure(service)` / `get_order_service()` pair
   in that same file.
3. In `main.py`, after `build_container()`, call each entrypoint module's `configure(...)`
   once at startup with the matching service off the container, instead of routing through
   a shared providers module.
4. Re-run `uv run arch-standard render-importlinter .` -- the ARCH-011 contract dropped its
   `providers` exemption, since every file under `entrypoints/` is now a genuine sibling.
5. Re-run `uv run arch-standard check .` to confirm ARCH-009/011 still pass.
6. If the project has web entrypoints, add a composition-root response-shaping mechanism
   (ARCH-057, SHOULD) if it doesn't already have one.

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
