# Rename `infrastructure` to `adapters` — Design Spec

- **Status:** Draft for review
- **Date:** 2026-09-21
- **Owner:** David Rodriguez
- **Amends:** `2026-09-05-architecture-standard-v1-design.md` (edited in place; that spec is kept current)

## 1. Decision

The outbound-adapter layer is renamed from `infrastructure` to `adapters`, in both
places it exists:

- per aggregate module: `<context>/<module>/infrastructure/` -> `<context>/<module>/adapters/`
- shared package: `commons.infrastructure` -> `commons.adapters` (`unit_of_work`, `outbox`, ...)

`entrypoints/` is unchanged. It stays a context-wide layer of **inbound (driving)
adapters**. `adapters/` holds the **outbound (driven) adapters**. No restructuring of
`entrypoints/` into `adapters/inbound` + `adapters/outbound` (considered, rejected: a
redesign of the entrypoints rules, template and import contracts, out of proportion to
a naming change).

Rule IDs and rule levels do not change. Only paths, names and prose change.

## 2. Compatibility and versioning

Clean break. Nothing is published (no tags on the remote) and no project repo consumes
the standard yet, so no legacy alias is built.

- The validator recognizes only `adapters/`. A project still using `infrastructure/`
  fails the normal structure checks; the migration note is the remedy.
- Catalog version `0.1.1` -> `0.2.0` in `pyproject.toml` and the catalog. Classified
  minor (paths renamed, no `level` change). `release-check` must accept it.
- `CHANGELOG.md` gets a `0.2.0` section marked breaking, with a migration note:
  `git mv <ctx>/<module>/infrastructure <ctx>/<module>/adapters`, update imports of
  `commons.infrastructure` to `commons.adapters`, re-run the validator.
- Left untouched, as records: `src/arch_standard/rules/_catalog/.released/0.1.0/`,
  `docs/superpowers/plans/*`, and the `0.1.x` CHANGELOG sections.

## 3. Scope of change

| Area | Change |
|---|---|
| Validator | `_MODULE_LAYER_DIRS` and `module_infrastructure_dir` -> `module_adapters_dir` (`checks/base.py`); `_MODULE_LAYERS`, ARCH-008/009/034 contract text and dependency names (`checks/import_contracts.py`) |
| Catalog | Examples and text in `dependencies`, `structure`, `model_integrity`, `application`, `cross_cutting` (current catalog only) |
| Template | `templates/src/{{ context_name }}/{{ aggregate_module }}/infrastructure/` directory, `bootstrap/__init__.py.jinja` imports, generated smoke test |
| `arch-commons` | `commons/infrastructure/` -> `commons/adapters/`; `tests/infrastructure/` -> `tests/adapters/`; `pyproject.toml` reference |
| Docs | `docs/standard/07-infrastructure.md` -> `07-adapters.md` with title and cross-references; all other `docs/standard/*.md`; the v1 design spec in place. `ARCHITECTURE_STANDARD.md` is regenerated with `docs`, never hand-edited |
| Tests / fixtures | `tests/checks/*`, `tests/rules/*`, `tests/templates/test_template_application_infrastructure.py` (renamed), `tests/fixtures/*` including `bad_project` |

## 4. Vocabulary

Stated once in `00-purpose` / `02-structure`, then used consistently:

- `adapters/` — outbound (driven) adapters: repositories, gateways, outbox, clients.
- `entrypoints/` — inbound (driving) adapters: HTTP, consumers, CLI.

No blind find-and-replace. "Infrastructure" also appears as generic prose ("infrastructure
concerns", "infrastructure adapters" where "adapters" now suffices); each hit is reviewed
and reworded or kept on its merits.

## 5. Testing

- Update tests that assert the old name first; watch them fail; rename source until they pass.
- Add a guard test, extending the existing stale-flat-path regression in
  `tests/rules/test_real_catalog.py`: no live catalog example and no template path may
  contain a `/infrastructure/` or `commons.infrastructure` segment.
- Final gates: pytest (root and `arch-commons`), ruff check, ruff format, mypy,
  `docs --check`, `release-check`, and the E2E distribution test.
- Work happens on `feat/rename-infrastructure-to-adapters`, branched from `master`.

## 6. Out of scope

- Restructuring `entrypoints/`.
- Any alias or deprecation window for the old name.
- Freezing a `.released/0.2.0/` baseline (a release action, still undecided under D3).
- The parked Plan 4 items.
