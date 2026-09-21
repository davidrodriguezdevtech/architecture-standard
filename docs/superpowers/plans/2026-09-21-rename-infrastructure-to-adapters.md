# Rename `infrastructure` to `adapters` Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rename the outbound-adapter layer from `infrastructure` to `adapters` (per-module `<context>/<module>/adapters/` and shared `commons.adapters`) across the validator, catalog, template, `arch-commons` package and docs, releasing catalog/`arch-standard` 0.2.0 and `arch-commons` 0.2.0.

**Architecture:** A mechanical rename driven test-first: each task updates the tests that assert the old name, watches them fail, then renames source until they pass. Prose is reviewed line by line (no blind find-and-replace of "infrastructure"). Version metadata, changelog and the regenerated `ARCHITECTURE_STANDARD.md` are handled explicitly.

**Tech Stack:** Python 3.12+, uv workspace, pytest, ruff, mypy, import-linter, copier, pydantic (rule model).

**Spec:** `docs/superpowers/specs/2026-09-21-rename-infrastructure-to-adapters-design.md` (read it first; this plan implements it).

## Global Constraints

- Branch: `feat/rename-infrastructure-to-adapters` (already created off `master`; do not commit to `master`).
- `entrypoints/` is **unchanged**. `adapters/` = outbound (driven) adapters; `entrypoints/` = inbound (driving) adapters.
- Rule IDs and rule `level`s do not change. Only paths, names and prose.
- Clean break: no alias, no dual-name support. The validator recognizes only `adapters/`.
- **Never edit**: `src/arch_standard/rules/_catalog/.released/0.1.0/**`, `docs/superpowers/plans/*` other than this file, the `0.1.0` and `0.1.1` sections of `CHANGELOG.md`, and `tests/checks/test_base.py` line 33 (a historical comment about removed method names).
- **Never hand-edit** `ARCHITECTURE_STANDARD.md`: regenerate with `uv run arch-standard docs`. `tests/test_self.py::test_committed_doc_matches_catalog` fails whenever the catalog or `docs/standard/*.md` change without regeneration, so every task that touches those regenerates and commits the file in the same commit.
- Versions: `arch-standard` `0.1.1` -> `0.2.0`; `arch-commons` `0.1.0` -> `0.2.0`.
- Every commit message ends with the trailer `Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>`. Pass it as a second `-m` argument.
- Shell is Git Bash (POSIX). Quote paths containing `{{ }}` and spaces. Run all commands from the repo root `C:\Users\David\dev\AI\architecture-standard`.
- `python` tooling always through `uv run`.

---

### Task 1: Validator recognizes `adapters/`

**Files:**
- Rename (git mv): `tests/fixtures/bad_project/src/sales/orders/infrastructure`, `tests/fixtures/good_project/src/sales/orders/infrastructure`, `tests/fixtures/modular_project/src/billing/invoices/infrastructure`, `tests/fixtures/modular_project/src/sales/orders/infrastructure`, `tests/fixtures/modular_project/src/sales/users/infrastructure` -> same paths ending in `adapters`
- Modify: `tests/fixtures/bad_project/src/sales/orders/domain/model/order.py:5`
- Modify: `tests/checks/test_base.py:65,91-92`
- Modify: `tests/checks/test_import_contracts.py` (10 occurrences)
- Modify: `src/arch_standard/checks/base.py:15,111-112`
- Modify: `src/arch_standard/checks/import_contracts.py` (15 occurrences)

**Interfaces:**
- Produces: `ProjectLayout.module_adapters_dir(context: str, module: str) -> Path` (replaces `module_infrastructure_dir`); `_MODULE_LAYER_DIRS == ("domain", "application", "adapters")`; import-linter contracts referencing `<context>.<module>.adapters` and `commons.adapters`.

- [ ] **Step 1: Rename the fixture directories (test data) and the import that names one**

```bash
git mv tests/fixtures/bad_project/src/sales/orders/infrastructure tests/fixtures/bad_project/src/sales/orders/adapters
git mv tests/fixtures/good_project/src/sales/orders/infrastructure tests/fixtures/good_project/src/sales/orders/adapters
git mv tests/fixtures/modular_project/src/billing/invoices/infrastructure tests/fixtures/modular_project/src/billing/invoices/adapters
git mv tests/fixtures/modular_project/src/sales/orders/infrastructure tests/fixtures/modular_project/src/sales/orders/adapters
git mv tests/fixtures/modular_project/src/sales/users/infrastructure tests/fixtures/modular_project/src/sales/users/adapters
sed -i '5s/sales\.orders\.infrastructure\.order_repository/sales.orders.adapters.order_repository/' tests/fixtures/bad_project/src/sales/orders/domain/model/order.py
```

Expected: line 5 of `order.py` reads `from sales.orders.adapters.order_repository import (  # ARCH-001 violation`.

- [ ] **Step 2: Update the tests to the new name**

`tests/checks/test_base.py` (only lines 65 and 91-92; leave the line-33 comment):

```bash
sed -i -e '65s/infrastructure/adapters/' -e '91s/module_infrastructure_dir/module_adapters_dir/' -e '92s/infrastructure/adapters/' tests/checks/test_base.py
```

Resulting lines: 65 `"src/sales/users/adapters/user_repository.py",`; 91-92 `layout.module_adapters_dir("sales", "users")` / `== root / "src/sales/users/adapters"`.

`tests/checks/test_import_contracts.py` — every occurrence (comments, `commons.infrastructure` strings, the test name, `(orders / "infrastructure")`, the import) is a rename target:

```bash
sed -i 's/infrastructure/adapters/g' tests/checks/test_import_contracts.py
grep -n "adapters" tests/checks/test_import_contracts.py
```

Expected: the test at old line 561 is now `test_given_an_entrypoint_importing_adapters__when_checked__then_arch_009_fails`; line ~580 is `"from sales.orders.adapters import Repo\n"`; lines ~385 `"from commons.adapters import x\n"`. Read the three comment hits (~52, ~96, ~132) and confirm each still reads grammatically (e.g. "importing its own adapters", "imports commons.adapters", "adapters FROM").

- [ ] **Step 3: Run the validator tests to verify they fail**

Run: `uv run pytest tests/checks tests/test_cli.py tests/test_empty_scan_safety.py -q`
Expected: FAIL. `AttributeError: 'ProjectLayout' object has no attribute 'module_adapters_dir'` in `test_base.py`, and import-contract / fixture-based tests failing because the source still looks for `infrastructure/`.

- [ ] **Step 4: Rename in `checks/base.py`**

```bash
sed -i -e '15s/infrastructure/adapters/' -e '111s/module_infrastructure_dir/module_adapters_dir/' -e '112s/infrastructure/adapters/' src/arch_standard/checks/base.py
```

Resulting: line 15 `_MODULE_LAYER_DIRS = ("domain", "application", "adapters")`; lines 111-112:

```python
    def module_adapters_dir(self, context: str, module: str) -> Path:
        return self.src / context / module / "adapters"
```

- [ ] **Step 5: Rename in `checks/import_contracts.py`**

```bash
sed -i 's/infrastructure/adapters/g' src/arch_standard/checks/import_contracts.py
```

Then fix what the substitution leaves ungrammatical or misnamed. Replace the ARCH-008 comment block (currently lines 30-34) with:

```python
#   - ARCH-008 (adapters implement ports; the core imports abstractions
#     only) is only half covered: this contract proves domain/application
#     import nothing from adapters/, but it does NOT verify that the
#     concrete adapters actually implement the Protocol declared in
#     the module's ``ports.py`` -- that half is unverified by any machine
#     check and is reviewed at PR time.
```

In `_module_contracts` (the ARCH-009 loop, ~lines 313-330) rename the local variable `infra` to `outbound` in its three uses (`infra = [`, `if infra:`, `*infra,`), and confirm the emitted strings read:

```python
            f"    {context}.{module}.adapters"
            for module in project.modules(context)
            if project.module_adapters_dir(context, module).is_dir()
```

```python
                f"name = ARCH-009 entrypoints do not touch adapters ({context})",
```

and in the ARCH-034 block:

```python
            "name = ARCH-034 commons.adapters isolated from domain and application",
            ...
            "    commons.adapters",
```

Also confirm the ARCH-046 tuple at ~line 164 is `for layer in ("application", "adapters")` and `_MODULE_LAYERS: tuple[str, ...] = ("adapters", "application", "domain")`.

Run: `grep -n -i infrastructure src/arch_standard/checks/base.py src/arch_standard/checks/import_contracts.py`
Expected: no output.

- [ ] **Step 6: Format, lint, type-check, and run the tests to verify they pass**

```bash
uv run ruff format . && uv run ruff check . && uv run mypy
uv run pytest tests/checks tests/test_cli.py tests/test_empty_scan_safety.py tests/test_outcome_semantics.py -q
uv run arch-standard check tests/fixtures/good_project
uv run arch-standard check tests/fixtures/modular_project
```

Expected: ruff/mypy clean; pytest PASS; both `check` commands exit 0. Then confirm the violation fixture still fails:

```bash
uv run arch-standard check tests/fixtures/bad_project; echo "exit=$?"
```

Expected: non-zero exit (`exit=1`), with ARCH-001 among the failures.

Then run everything except the template tests:

```bash
uv run pytest -q --ignore=tests/templates
```

Expected: PASS. `tests/templates` is **expected to be red** until Task 3: generated projects still contain `infrastructure/`, which the validator no longer recognizes. Any failure outside `tests/templates` means a missed rename: fix it before committing.

- [ ] **Step 7: Commit**

```bash
git add -A tests/fixtures tests/checks src/arch_standard/checks
git commit -m "refactor: validator recognizes the adapters layer instead of infrastructure" -m "Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>"
```

---

### Task 2: `arch-commons` exposes `commons.adapters`

**Files:**
- Rename (git mv): `packages/arch-commons/src/commons/infrastructure` -> `packages/arch-commons/src/commons/adapters`; `packages/arch-commons/tests/infrastructure` -> `packages/arch-commons/tests/adapters`
- Modify: `packages/arch-commons/tests/adapters/test_sqlalchemy_unit_of_work.py:37,52`, `test_outbox.py:11,18,42`, `test_leaf_adapters.py:7-10`
- Modify: `packages/arch-commons/pyproject.toml:4`

**Interfaces:**
- Produces: importable modules `commons.adapters.{in_memory_event_bus, in_memory_unit_of_work, outbox, sqlalchemy_unit_of_work, system_clock, uuid7_id_generator}` with unchanged contents (only their package name changes). Task 3's template imports these.

- [ ] **Step 1: Rename the tests directory and update its imports (tests first)**

```bash
git mv packages/arch-commons/tests/infrastructure packages/arch-commons/tests/adapters
sed -i 's/commons\.infrastructure/commons.adapters/g' packages/arch-commons/tests/adapters/test_sqlalchemy_unit_of_work.py packages/arch-commons/tests/adapters/test_outbox.py packages/arch-commons/tests/adapters/test_leaf_adapters.py
```

- [ ] **Step 2: Run the package tests to verify they fail**

Run: `uv run --package arch-commons pytest -c packages/arch-commons/pyproject.toml packages/arch-commons/tests -q`
Expected: FAIL with `ModuleNotFoundError: No module named 'commons.adapters'`.

- [ ] **Step 3: Rename the source package and its description**

```bash
git mv packages/arch-commons/src/commons/infrastructure packages/arch-commons/src/commons/adapters
sed -i '4s/commons\.infrastructure/commons.adapters/' packages/arch-commons/pyproject.toml
```

Line 4 of `packages/arch-commons/pyproject.toml` must read: `description = "Architecture Standard — shared technical package (commons.types, commons.adapters)"`.

- [ ] **Step 4: Run the package gates to verify they pass**

```bash
uv run --package arch-commons ruff format packages/arch-commons
uv run --package arch-commons ruff check packages/arch-commons
uv run --package arch-commons mypy --config-file packages/arch-commons/pyproject.toml packages/arch-commons/src packages/arch-commons/tests
uv run --package arch-commons pytest -c packages/arch-commons/pyproject.toml packages/arch-commons/tests -q
grep -rn -i infrastructure packages/arch-commons --include=*.py --include=*.toml
```

Expected: all clean/PASS (23 tests, as before); the `grep` prints nothing.

- [ ] **Step 5: Commit**

```bash
git add -A packages/arch-commons
git commit -m "refactor: arch-commons exposes commons.adapters instead of commons.infrastructure" -m "Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>"
```

---

### Task 3: Template generates `adapters/` and imports `commons.adapters`

**Files:**
- Rename (git mv): `templates/src/{{ context_name }}/{{ aggregate_module }}/infrastructure` -> `.../adapters`; `tests/templates/test_template_application_infrastructure.py` -> `tests/templates/test_template_application_adapters.py`
- Modify: `templates/src/bootstrap/__init__.py.jinja:5-7,12`
- Modify: `templates/tests/test_{{ aggregate_module }}_smoke.py.jinja:3-5,12`
- Modify: `templates/src/{{ context_name }}/{{ aggregate_module }}/adapters/{{ aggregate_name }}_repository.py.jinja:3`
- Modify: `tests/templates/test_template_application_adapters.py`

**Interfaces:**
- Consumes: `commons.adapters.*` from Task 2; `module_adapters_dir` layout recognition from Task 1 (the generated-project end-to-end test runs the validator on generated output).
- Produces: generated projects containing `src/<context>/<module>/adapters/<aggregate>_repository.py`.

- [ ] **Step 1: Rename the test file, update it, and add the template guard test**

```bash
git mv tests/templates/test_template_application_infrastructure.py tests/templates/test_template_application_adapters.py
```

Edit `tests/templates/test_template_application_adapters.py`:

1. Rename the test function to `test_given_defaults__when_copied__then_application_and_adapters_files_compile`.
2. Change the repository path line to `repository_path = dest / "src/sales/orders/adapters/order_repository.py"`.
3. Add `import re` to the imports (alphabetical: `import py_compile`, `import re`) and append this test at the end of the file:

```python
_OLD_LAYER = re.compile(r"\.infrastructure\b|\binfrastructure/")


def test_given_the_template_tree__when_scanned__then_no_infrastructure_layer_remains() -> None:
    offenders: list[str] = []
    for path in TEMPLATE_ROOT.rglob("*"):
        relative = path.relative_to(TEMPLATE_ROOT)
        if "infrastructure" in relative.parts:
            offenders.append(f"path: {relative}")
        if path.is_file() and _OLD_LAYER.search(path.read_text(encoding="utf-8")):
            offenders.append(f"content: {relative}")
    assert offenders == []
```

- [ ] **Step 2: Run to verify it fails**

Run: `uv run pytest tests/templates/test_template_application_adapters.py -q`
Expected: FAIL. The compile test with `FileNotFoundError` on `.../orders/adapters/order_repository.py`; the guard test listing the `infrastructure` template directory and the three `.jinja` files.

- [ ] **Step 3: Rename the template directory and its imports**

```bash
git mv "templates/src/{{ context_name }}/{{ aggregate_module }}/infrastructure" "templates/src/{{ context_name }}/{{ aggregate_module }}/adapters"
sed -i -e 's/commons\.infrastructure/commons.adapters/g' -e 's/\.infrastructure\./.adapters./g' "templates/src/bootstrap/__init__.py.jinja" "templates/tests/test_{{ aggregate_module }}_smoke.py.jinja" "templates/src/{{ context_name }}/{{ aggregate_module }}/adapters/{{ aggregate_name }}_repository.py.jinja"
grep -rn -i infrastructure templates
```

Expected: `grep` prints nothing. Spot-check `templates/src/bootstrap/__init__.py.jinja` line 12 reads `from {{ context_name }}.{{ aggregate_module }}.adapters.{{ aggregate_name }}_repository import (`.

- [ ] **Step 4: Run all template tests and lint**

```bash
uv run ruff format . && uv run ruff check . && uv run mypy
uv run pytest tests/templates -q
```

Expected: PASS, including `test_generated_project_end_to_end.py` (which generates a project and runs the validator and its tests). If the end-to-end test fails on `commons.adapters` not found, Task 2 was not applied to the installed workspace: run `uv sync` and retry.

- [ ] **Step 5: Commit**

```bash
git add -A templates tests/templates
git commit -m "refactor: template generates adapters/ and imports commons.adapters" -m "Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>"
```

---

### Task 4: Rule catalog and guard test

**Files:**
- Modify: `tests/rules/test_real_catalog.py:11-14` (and add a guard test)
- Modify: `src/arch_standard/rules/_catalog/{dependencies,structure,model_integrity,application,cross_cutting,progressive_structure}.yaml`
- Modify: `tests/rules/test_model.py:14,18,21`, `tests/fixtures/rules_ok/sample.yaml:3,7,10` (schema sample data, kept consistent with the new vocabulary)
- Regenerate: `ARCHITECTURE_STANDARD.md`

**Interfaces:** none new. `testing.yaml` has no hits and is untouched. `.released/0.1.0/*` is never touched.

- [ ] **Step 1: Update the flat-path regression and add the old-name guard (tests first)**

In `tests/rules/test_real_catalog.py`, change the regex comment and pattern (lines 11-14) to:

```python
# A context name directly followed by domain/application/adapters (no
# aggregate module segment in between) is the pre-aggregate-module flat
# shape the standard no longer uses (spec §17 row P).
FLAT_CONTEXT_PATH = re.compile(r"\b(?:sales|billing)[./](?:domain|application|adapters)\b")

# The layer's pre-0.2.0 name. Catches path-like uses only ("infrastructure/",
# ".infrastructure", "/infrastructure"); generic prose is reviewed by hand.
OLD_LAYER_NAME = re.compile(r"\binfrastructure/|\.infrastructure\b|/infrastructure\b")
```

Append this test (after `test_given_the_catalog__when_reading_examples__then_no_stale_flat_context_paths`):

```python
def test_given_the_catalog__when_reading_any_text__then_no_infrastructure_layer_path() -> None:
    cat = Catalog.load(RULES_DIR)
    for rule in cat:
        text = "\n".join(
            [
                rule.name,
                rule.description,
                rule.rationale,
                rule.correct,
                rule.incorrect,
                rule.validation.detail or "",
            ]
        )
        match = OLD_LAYER_NAME.search(text)
        assert match is None, (
            f"{rule.id} still names the layer 'infrastructure' ({match.group(0) if match else '?'}); "
            "the layer is called 'adapters' since 0.2.0"
        )
```

(If `RULES_DIR` is not the module-level name in that file, use the same constant the neighbouring tests use to load the catalog — it is `RULES_DIR = packaged_rules_dir()` at the top of the file.)

- [ ] **Step 2: Run to verify it fails**

Run: `uv run pytest tests/rules/test_real_catalog.py -q`
Expected: FAIL on the new guard test, citing ARCH-001 (and others).

- [ ] **Step 3: Rewrite the catalog — path-like forms first**

Apply to the six catalog files (never `.released/`):

```bash
cd src/arch_standard/rules/_catalog
sed -i -e 's#/infrastructure#/adapters#g' -e 's#infrastructure/#adapters/#g' -e 's#\.infrastructure\b#.adapters#g' dependencies.yaml structure.yaml model_integrity.yaml application.yaml cross_cutting.yaml progressive_structure.yaml
cd ../../../..
grep -n -i infrastructure src/arch_standard/rules/_catalog/*.yaml
```

Expected: the remaining hits are only prose, listed in Step 4.

- [ ] **Step 4: Rewrite the remaining prose by hand**

Apply each substitution to the named file, then re-run the `grep`; it must print nothing.

| File | Old | New |
|---|---|---|
| `dependencies.yaml` (rule name) | `Domain does not depend on infrastructure` | `Domain does not depend on adapters` |
| `dependencies.yaml` (rule name) | `Application does not depend on infrastructure` | `Application does not depend on adapters` |
| `dependencies.yaml` (rule name) | `Infrastructure implements ports; the core imports abstractions only` | `Adapters implement ports; the core imports abstractions only` |
| `dependencies.yaml` (rule name) | `never construct or call infrastructure directly` | `never construct or call adapters directly` |
| `dependencies.yaml` (rule name) | `application, infrastructure, or shared_kernel` | `application, adapters, or shared_kernel` |
| `dependencies.yaml` (~142) | `infrastructure adapter class such as` | `adapter class such as` |
| `dependencies.yaml` (~189) | `infrastructure adapter or calls` | `adapter or calls` |
| `dependencies.yaml` (~169) | `infrastructure plugs in behind` | `adapters plug in behind` |
| `structure.yaml` (~26) | `application and infrastructure` | `application and adapters` |
| `cross_cutting.yaml` (~54) | `infrastructure adapters log` | `outbound adapters log` |

Read each edited sentence in context (the lines before and after) to make sure the article still fits ("an adapter class", "an adapter or calls"); fix the article if not. Also confirm the rule at `dependencies.yaml` ~line 379 now reads `name: commons/adapters is not imported by domain or application`.

- [ ] **Step 5: Keep the schema sample data consistent**

```bash
sed -i -e 's/Domain independent of infrastructure/Domain independent of adapters/' -e 's/does not import the infrastructure layer/does not import the adapters layer/' -e 's/sales\.infrastructure\.postgres/sales.adapters.postgres/' tests/rules/test_model.py tests/fixtures/rules_ok/sample.yaml
grep -n -i infrastructure tests/rules/test_model.py tests/fixtures/rules_ok/sample.yaml
```

Expected: no output.

- [ ] **Step 6: Regenerate the standard and run the rule tests**

```bash
uv run arch-standard docs
uv run pytest tests/rules tests/test_self.py tests/test_docgen.py tests/test_packaged_catalog.py -q
uv run arch-standard docs --check
```

Expected: PASS. `test_docgen.py` still expects the `07-infrastructure` file stem; that is renamed in Task 5, and it must pass here because the doc file has not been renamed yet.

- [ ] **Step 7: Full gates, then commit**

```bash
uv run ruff format . && uv run ruff check . && uv run mypy && uv run pytest -q
git add -A src/arch_standard/rules tests/rules tests/fixtures/rules_ok ARCHITECTURE_STANDARD.md
git commit -m "refactor: rule catalog names the adapters layer; guard against the old name" -m "Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>"
```

Expected: everything PASS before the commit.

---

### Task 5: Standard prose and living design spec

**Files:**
- Rename (git mv): `docs/standard/07-infrastructure.md` -> `docs/standard/07-adapters.md`
- Modify: `tests/test_docgen.py:19`
- Modify: `docs/standard/{00-purpose,01-philosophy,02-structure,03-bounded-contexts,04-entry-points,05-domain,06-application,07-adapters,08-commons-shared-kernel,10-ddd-rules,12-anti-patterns,15-progressive-structure}.md`
- Modify: `docs/superpowers/specs/2026-09-05-architecture-standard-v1-design.md` (lines 1-1128 plus the two rows below; rows G, L, P, Q at lines 1136-1146 are historical and stay)
- Regenerate: `ARCHITECTURE_STANDARD.md`

- [ ] **Step 1: Update the docgen expectation (test first) and see it fail**

In `tests/test_docgen.py` change `"07-infrastructure",` to `"07-adapters",`.

Run: `uv run pytest tests/test_docgen.py -q`
Expected: FAIL (`test_every_prose_partial_exists`: `07-infrastructure` found, `07-adapters` missing).

- [ ] **Step 2: Rename the section file and rewrite path-like forms**

```bash
git mv docs/standard/07-infrastructure.md docs/standard/07-adapters.md
sed -i -e 's#commons\.infrastructure#commons.adapters#g' -e 's#commons/infrastructure#commons/adapters#g' -e 's#infrastructure/#adapters/#g' docs/standard/*.md
sed -i -e '1,1128{s#commons\.infrastructure#commons.adapters#g;s#commons/infrastructure#commons/adapters#g;s#infrastructure/#adapters/#g}' docs/superpowers/specs/2026-09-05-architecture-standard-v1-design.md
grep -n -i infrastructure docs/standard/*.md
```

Expected: the remaining `docs/standard` hits are exactly the prose lines in Step 3.

- [ ] **Step 3: Rewrite the remaining prose by hand**

Apply each to `docs/standard/` and to the same sentence in the v1 design spec (`grep -n -i infrastructure docs/superpowers/specs/2026-09-05-architecture-standard-v1-design.md` lists them; ignore lines 1136-1146):

| Where | Old | New |
|---|---|---|
| `07-adapters.md:1` and spec `## 7. Infrastructure layer` | `# 7. Infrastructure` / `## 7. Infrastructure layer` | `# 7. Adapters` / `## 7. Adapters layer` |
| `00-purpose` (~44), spec (~30) | `at infrastructure and transport boundaries` / `at adapters/transport boundaries` (Step 2's path substitution already turned the spec's `infrastructure/transport` into this) | `at adapter and transport boundaries` / `at adapter/transport boundaries` |
| `00-purpose` (~77), spec (~41, ~774) | `entrypoints and infrastructure adapters log` / `Logging happens in entrypoints and infrastructure adapters` | `entrypoints and outbound adapters log` / `Logging happens in entrypoints and outbound adapters` |
| `01-philosophy` (~10), spec (~54) | `` `infrastructure -> domain/application` `` / `` `infrastructure → domain/application` `` | `` `adapters -> domain/application` `` / `` `adapters → domain/application` `` |
| `01-philosophy` (~11), spec (~55) | `Infrastructure is plugged in, never imported` | `Adapters are plugged in, never imported` |
| `03-bounded-contexts` (~48), spec (~257) | `Because infrastructure is behind ports` | `Because adapters sit behind ports` |
| `04-entry-points` (~18), spec (~334) | `construct infrastructure` | `construct outbound` (reads "construct outbound adapters itself") |
| `04-entry-points` (~30), spec (~347) | `read infrastructure state directly` | `read backing-service state directly` |
| `05-domain` (~74), `10-ddd-rules` (~92) | `(that is application or infrastructure)` | `(that is an application or adapter concern)` |
| `06-application` (~69), spec (~509) | `the core must not name infrastructure` | `the core must not name adapters` |
| `12-anti-patterns` (~11), spec (~912) | `Domain imports infrastructure / frameworks` and `infra implements` | `Domain imports adapters / frameworks` and `adapters implement` |
| `15-progressive-structure` (~16), spec (~997) | `Infrastructure adapters of one kind` | `Outbound adapters of one kind` |
| spec (~755) ARCH-008 row | `Infrastructure implements ports; the core imports abstractions only` | `Adapters implement ports; the core imports abstractions only` |
| spec (~756) ARCH-009 row | `never construct or call infrastructure directly` | `never construct or call adapters directly` |
| spec (~1081) section list | `7.  Infrastructure — outbound adapters; data mapper; UoW; outbox` | `7.  Adapters — outbound adapters; data mapper; UoW; outbox` |

Then `grep -n -i infrastructure docs/standard/*.md` must print nothing, and the same grep on the v1 spec must show only lines 1136-1146 (rows G, L, P, Q).

- [ ] **Step 4: State the vocabulary once**

In `docs/standard/02-structure.md`, immediately after the closing code fence of the folder tree and before the paragraph starting `` `commons/` is not part of `src/` ``, insert:

```markdown
`adapters/` holds a module's **outbound (driven) adapters**: repositories, gateways,
clients. `entrypoints/` holds the context's **inbound (driving) adapters**: HTTP, consumers,
CLI. Both are adapters; the folder names say which side of the core they sit on.

```

Insert the identical paragraph in the same relative position in the v1 design spec (after the tree in its Section 2, before its `` `commons/` is not part of `src/` `` paragraph).

- [ ] **Step 5: Record the change in the spec's trade-off table**

Append this row directly after row R (the last row, ~line 1147 of the v1 design spec), matching the table's `| Letter | Topic | Resolution |` shape:

```markdown
| S | ~~Layer named `infrastructure`~~ RESOLVED | Renamed to `adapters` (per module) and `commons.adapters` (shared) in catalog/`arch-standard` 0.2.0 and `arch-commons` 0.2.0, as a clean break with no alias. `entrypoints/` is unchanged and remains the inbound side. Rows G, L, P, Q above describe earlier states and keep the old name as history. See `2026-09-21-rename-infrastructure-to-adapters-design.md`. |
```

- [ ] **Step 6: Regenerate and verify**

```bash
uv run arch-standard docs
uv run pytest tests/test_docgen.py tests/test_self.py -q
uv run arch-standard docs --check
uv run ruff format . && uv run ruff check . && uv run mypy && uv run pytest -q
```

Expected: PASS, `docs --check` exits 0. Skim `git diff ARCHITECTURE_STANDARD.md` for one section to confirm the heading `# 7. Adapters` and the vocabulary paragraph rendered.

- [ ] **Step 7: Commit**

```bash
git add -A docs tests/test_docgen.py ARCHITECTURE_STANDARD.md
git commit -m "docs: standard and design spec name the adapters layer and its inbound/outbound vocabulary" -m "Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>"
```

---

### Task 6: Release 0.2.0 metadata and changelog

**Files:**
- Modify: `pyproject.toml:3`, `packages/arch-commons/pyproject.toml:3`, `templates/copier.yml:29,34`, `tests/templates/test_template_version_defaults.py:25-27` (comment), `CHANGELOG.md` (new section at top), `uv.lock`

**Interfaces:** `tests/templates/test_template_version_defaults.py` requires `templates/copier.yml`'s `arch_standard_version` / `arch_commons_version` defaults to equal each package's own `pyproject.toml` version; both pairs move together in this task.

- [ ] **Step 1: Bump the versions (this is the "failing test": the pairs must move together)**

```bash
sed -i '3s/version = "0.1.1"/version = "0.2.0"/' pyproject.toml
sed -i '3s/version = "0.1.0"/version = "0.2.0"/' packages/arch-commons/pyproject.toml
sed -i -e '29s/default: "0.1.1"/default: "0.2.0"/' -e '34s/default: "0.1.0"/default: "0.2.0"/' templates/copier.yml
sed -n '27,35p' templates/copier.yml
```

Expected: `arch_standard_version` default `"0.2.0"` (line 29) and `arch_commons_version` default `"0.2.0"` (line 34); `template_version` (line ~39) stays `"0.1.0"`.

Update the now-stale comment in `tests/templates/test_template_version_defaults.py` (lines 25-27): replace `(0.1.1 vs 0.1.0 as of this writing)` with `(they may legitimately diverge)`.

- [ ] **Step 2: Refresh the lockfile and confirm the metadata**

```bash
uv lock
uv sync
uv run python -c "import importlib.metadata as m; print(m.version('arch-standard'), m.version('arch-commons'))"
```

Expected: `0.2.0 0.2.0`. `git diff uv.lock` shows only the two workspace-package version lines changing.

- [ ] **Step 3: Verify the compatibility policy accepts the bump**

Run: `uv run arch-standard release-check --version 0.2.0`
Expected: exit 0, a line of the form `OK 0.1.0 -> 0.2.0 (minor bump, N rule change(s))`. Record the exact line; it goes in the changelog. If it reports an unsanctioned MUST promotion or a failure, stop: a `level` was changed by accident in Task 4 (`git diff master -- src/arch_standard/rules/_catalog`).

- [ ] **Step 4: Write the changelog entry**

In `CHANGELOG.md`, insert this section immediately above `## 0.1.1`, substituting the exact `OK ...` line captured in Step 3:

````markdown
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

Classified **minor** per spec Section 16.3; `uv run arch-standard release-check --version 0.2.0`
confirms: `<paste the OK line from Step 3 here>`.

#### Migration notes

For each existing project:

1. `git mv src/<context>/<module>/infrastructure src/<context>/<module>/adapters` for every
   aggregate module.
2. Replace imports: `<context>.<module>.infrastructure` -> `<context>.<module>.adapters`, and
   `commons.infrastructure` -> `commons.adapters` (requires `arch-commons` >= 0.2.0).
3. Re-run `arch-standard check .`. A project still using `infrastructure/` is reported by the
   normal structure checks.

````

- [ ] **Step 5: Verify and commit**

```bash
uv run pytest tests/templates/test_template_version_defaults.py tests/rules/test_real_catalog.py -q
uv run ruff format . && uv run ruff check . && uv run mypy && uv run pytest -q
git add -A pyproject.toml packages/arch-commons/pyproject.toml templates/copier.yml tests/templates/test_template_version_defaults.py CHANGELOG.md uv.lock
git commit -m "chore: release 0.2.0 (adapters layer rename) with changelog and migration notes" -m "Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>"
```

Expected: PASS before the commit.

---

### Task 7: Whole-branch verification

**Files:** none modified unless a check fails.

- [ ] **Step 1: No live occurrence of the old name remains**

```bash
git grep -n -i infrastructure -- . \
  ':!src/arch_standard/rules/_catalog/.released' \
  ':!docs/superpowers/plans' \
  ':!CHANGELOG.md' \
  ':!uv.lock'
```

Expected: only these remain, all intentional: the rename spec (`2026-09-21-rename-...-design.md`), rows G/L/P/S of the v1 design spec, `tests/checks/test_base.py:33` (historical comment), the guard-test regexes and messages in `tests/rules/test_real_catalog.py` and `tests/templates/test_template_application_adapters.py`. Anything else is a missed rename: fix it in the matching task's area and amend nothing; make a new commit.

- [ ] **Step 2: The frozen baseline and history are untouched**

```bash
git diff master --stat -- src/arch_standard/rules/_catalog/.released docs/superpowers/plans
```

Expected: only `docs/superpowers/plans/2026-09-21-rename-infrastructure-to-adapters.md` (this plan) appears; nothing under `.released/`.

- [ ] **Step 3: Run every CI gate locally**

```bash
uv sync
uv run ruff check . && uv run ruff format --check . && uv run mypy
uv run pytest -q
uv run --package arch-commons ruff check packages/arch-commons
uv run --package arch-commons ruff format --check packages/arch-commons
uv run --package arch-commons mypy --config-file packages/arch-commons/pyproject.toml packages/arch-commons/src packages/arch-commons/tests
uv run --package arch-commons pytest -c packages/arch-commons/pyproject.toml packages/arch-commons/tests -q
uv run arch-standard docs --check
uv run arch-standard check tests/fixtures/good_project
uv run arch-standard check tests/fixtures/modular_project
uv run arch-standard release-check --version "$(uv run python -c 'import importlib.metadata as m; print(m.version("arch-standard"))')"
make e2e
```

Expected: all exit 0 (root suite previously 172 passed plus this branch's two new guard tests; arch-commons 23 passed). `bad_project` must still fail:

```bash
uv run arch-standard check tests/fixtures/bad_project; echo "exit=$?"
```

Expected: `exit=1`.

If `make e2e` cannot run in this environment (no network for `uv build` dependencies), say so explicitly in the report instead of claiming it passed.

- [ ] **Step 4: Report**

Summarize, with the actual command output: gate results, the final `release-check` line, and the `git log --oneline master..HEAD` list. Do not merge; hand the branch back for the finishing-a-development-branch decision.
