# Changelog

All notable changes to the Architecture Standard's rule catalog are recorded here,
one version per section. The compatibility policy (spec Section 16.3) governs
what kind of change requires which version bump; `arch-standard release-check`
enforces it in CI on every push and pull request, `arch-standard changelog`
renders these entries.

## 1.0.0

**The first real release.** Every version before this one was informal: `0.2.0` was
a retroactive snapshot of a catalog that was never actually frozen or tagged, and
`0.3.0`/`0.4.0` were built and consumed by several concurrent sessions directly off
branch tips (see `CONTRIBUTING.md`), sometimes under a number that had already been
claimed for different content. Nothing about this project's maturity or scope
changed today — this version exists to say, honestly, that from here on a version
number means one specific, frozen thing, and the rule catalog's own promotion
discipline is being followed for real for the first time.

**Promoted: ARCH-055 (every Python package directory has an `__init__.py`) — SHOULD
becomes MUST.** A missing `__init__.py` now fails `arch-standard check` outright
instead of warning. The gap this closes is concrete: `SHOULD` findings don't fail
anything, so a directory scaffolded without one was easy to create and easy to never
notice — nothing forced a second look.

This is why the version is `1.0.0` and not `0.5.0`. The compatibility policy (spec
Section 16.3) only sanctions a `SHOULD -> MUST` promotion as a minor bump when the
rule was genuinely `SHOULD` in the immediately preceding *released* snapshot.
ARCH-055 didn't exist at all in the only snapshot this project has ever actually
frozen (`0.2.0`, and even that was retroactive) — so by the tool's own
`release-check`, this is classified as a rule arriving already binding, which
requires a major bump, not a promotion. Rather than fudge the version to dodge that
signal, or promote it anyway and call it `0.5.0`, this releases `1.0.0` for real:
the catalog as it exists today, including ARCH-055 as MUST, is the actual first
frozen baseline. Every rule promoted to MUST from here on will have been SHOULD in
*this* snapshot first, so the minor-bump promotion path finally means what it says.

### Changed
- ARCH-055: `SHOULD` -> `MUST`. No wording change beyond the level itself; the
  description already covered the `commons/`/`commons/adapters/` namespace exceptions
  correctly. `validation.detail` corrected to mention the `commons/adapters/`
  exception explicitly (it only named `commons/` before) -- a stale-text fix, not a
  behaviour change.

No other rule's id, level, or enforced behaviour changed in this release.

#### Migration notes

For each existing project pinned below `1.0.0`:

1. Run `uv run arch-standard check .` before upgrading the pin. If ARCH-055 already
   shows PASS (no findings), the upgrade is a no-op for you.
2. If it shows WARN with findings, add the missing `__init__.py` files it lists
   before upgrading -- after the pin moves, the same findings become FAIL and block
   the verification gate.
3. Bump the pin in `pyproject.toml` and `.arch-standard` to `1.0.0`, rebuild/reinstall
   from a wheel built off `master` (see `CONTRIBUTING.md` -- never off a branch tip).

## 0.4.0

**Renumbered from 0.3.0.** Everything below this line was developed and consumed,
across several sessions, under the version number `0.3.0` -- but that number was
never actually released (no tag, `master` sat frozen at `0.2.0` the whole time), and
at least one of those sessions amended already-in-progress catalog content without
bumping the number, so `0.3.0` came to mean different things depending on when a
consumer built its wheel. Several projects had already pinned `0.3.0` in
`.arch-standard` against one of those intermediate states. Renumbering the whole
accumulated set to `0.4.0` makes every one of those pins unambiguous again: a
project still pinned to `0.3.0` keeps whatever it already has, and picking up
anything below requires deliberately moving the pin to `0.4.0`. Nothing below this
line was rewritten for the renumber -- it is exactly what was already recorded
under `0.3.0`, all classified `minor` by the compatibility policy, unified under
one version because none of it was ever actually released separately.

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

**Added: `commons/adapters/`, the project's own carve-out for framework-bound
technical adapters shared across contexts (ARCH-047, ARCH-059).** A technical
adapter that would belong in `arch-commons`' `commons.adapters` but is not (yet)
proposed upstream, or is specific enough to one project that upstreaming never
applies (a request-scoped `UnitOfWork` tuned to one project's concurrency model, for
instance), now has a documented home: `src/commons/adapters/`, this project's own
mirror of `arch-commons`' `commons.adapters` portion (Section 8.3). It merges with
that portion at import time exactly the way `commons/` merges with `commons.types`
and `commons.adapters` as a whole, so `commons/adapters/` is the second directory
under `src/` that MUST NOT have an `__init__.py` (ARCH-055) -- which required
removing `commons/adapters/__init__.py` from `arch-commons` itself, since a regular
package on either side would keep shadowing the other rather than merging with it
(verified empirically: with `arch-commons`' `__init__.py` in place, a project's own
`commons/adapters/<name>.py` is not importable at all, not even silently broken --
`ModuleNotFoundError`). `commons/adapters/` follows adapters/-layer discipline
throughout: framework imports are allowed (ARCH-003 does not apply there), the
`*Service`/`*Repository` name-suffix ban does not apply (ARCH-047), and mutation is
expected. It never holds a port (that stays upstream, in `commons/types/`, per the
three-homes rule, ARCH-042), an aggregate, or business logic.

**Added: bootstrap/ wires adapters, it does not define them (ARCH-059, SHOULD).** A
class defined under `bootstrap/` that directly subclasses a name imported from
`commons.types` or `commons.adapters` is adapter-shaped code sitting in the
composition root instead of an adapters/ directory -- it runs correctly either way,
which is exactly why this needed a checked rule rather than relying on every future
PR noticing. This closes the gap that let a real UnitOfWork implementation end up in
`bootstrap/unit_of_work.py`, working, but invisible to every context that could
otherwise import it from `commons/adapters/`.

### Added
- ARCH-059 (SHOULD) -- bootstrap/ wires adapters, it does not define them

### Changed
- ARCH-047: gains the `commons/adapters/` carve-out (framework-bound technical
  adapters shared across contexts), alongside the existing `commons/services.py`
  carve-out; the name-suffix ban and mutation check do not apply inside it
- ARCH-003: gains a second exception -- `commons/adapters/`, when it exists, follows
  adapters/-layer discipline throughout and is exempt from the framework-import ban
  entirely, not just the scalar-validator allowlist
- ARCH-055: gains a second inverted case -- `commons/adapters/`, mirroring
  `commons/` itself, MUST NOT have an `__init__.py`

No rule `level` changed; no rule `id` was removed.

#### Migration notes (commons/adapters/)

For each existing project with a framework-bound technical adapter, shared across
contexts, sitting somewhere other than its documented home (most commonly
`bootstrap/`, since `bootstrap/` can import anything and the code runs fine there):

1. Upgrade to `arch-commons` 0.4.0 or later (the version that first ships
   `commons/adapters/` without its own `__init__.py`).
2. Move the adapter to `src/commons/adapters/<name>.py`. Do not add an
   `__init__.py` to `src/commons/adapters/` itself; do add one to any directory
   nested under it, as normal (ARCH-055).
3. Update every import site from the old location to
   `commons.adapters.<name>`.
4. Re-run `uv run arch-standard check .` to confirm ARCH-003, ARCH-047, ARCH-055
   and ARCH-059 all pass.

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
