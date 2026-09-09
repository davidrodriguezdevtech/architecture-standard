# Plan 3.1 — Architecture Standard v1 Release Hardening

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Close the nine blocking findings from the v1 Acceptance Audit so the Architecture Standard is honest (the catalog never claims enforcement it does not have), distributable (an installed wheel works outside a source checkout), deterministic (no vacuous green, no crash that looks like a violation), and provably so via a subprocess end-to-end test — enough to declare `ARCHITECTURE STANDARD v1 STATUS: READY`.

**Architecture:** Three independent seams. (1) *Catalog packaging* — the rule YAML moves inside the `arch_standard` package and is resolved with `importlib.resources`, so dev and installed runs are byte-identical; `Catalog.load` raises instead of silently returning an empty catalog. (2) *Validator honesty* — the `Outcome` enum grows `ERROR` and `NOT_AUTOMATED`, the full run reports every catalog rule (never silently omitting one), checks that scanned nothing report `SKIP` rather than `PASS`, and a meta-test makes it impossible for a rule to claim a machine validator it does not have. (3) *Distribution* — the template's dependency source becomes a real prompt with no placeholder default, and a subprocess test builds both wheels, installs them into a clean environment, generates a project, and runs its gates without ever touching the monorepo's `sys.path`.

**Tech Stack:** Python 3.12+, `uv` workspaces, `hatchling`, `pytest`, `pydantic` v2, `PyYAML`, `tomllib` (stdlib), `importlib.resources` (stdlib), `import-linter` + `grimp`, `ruff`, `mypy --strict`, `copier>=9`.

**Spec:** `docs/superpowers/specs/2026-09-05-architecture-standard-v1-design.md` — read Section 0 (Distribution row), Section 9 (rule tiers; "Core (12 rules) — binding from day one, all machine-checkable"), Section 13 (MUST/SHOULD/MAY and the ADR exception process), Section 14.2 (automation confidence tiers — `full` is defined as "deterministic pass/fail on the exact rule"), Section 16.3 (versioning and distribution — the compatibility table and the **verbatim** `.arch-standard` stamp shape), Section 17 rows H/J/R (all three are the audit findings this plan closes).

**Source of truth for scope:** the v1 Acceptance Audit (this conversation). Its nine BLOCKER/HIGH items map to Tasks 1–15 below.

**Not in this plan (explicit non-goals — do not implement, do not "fix while you're in there"):** H5 UnitOfWork contract divergence; H6 missing shared contract tests; H7 the canonical example's ARCH-019 warning; H8 version-safety holes (`majors_crossed` ahead-case, `actual_bump` ordering); H9 the ARCH-030 wording contradiction; H10 stale pre-aggregate-module prose in `docs/standard/`; every M1–M9; the Software Factory; the Superpowers architecture skill; the architecture-reviewer agent; multi-agent orchestration. If one of these blocks a task, stop and report it rather than expanding scope.

## Global Constraints

- Python 3.12+. `from __future__ import annotations` at the top of every module.
- Root repo passes `uv run ruff check .`, `uv run ruff format --check .`, `uv run mypy` (strict), `uv run pytest`, `uv run arch-standard docs --check`. `packages/arch-commons` is a separate workspace member checked via `uv run --package arch-commons ruff check packages/arch-commons`, `uv run --package arch-commons mypy --config-file packages/arch-commons/pyproject.toml packages/arch-commons/src packages/arch-commons/tests`, and `uv run --package arch-commons pytest -c packages/arch-commons/pyproject.toml packages/arch-commons/tests`.
- Run `uv run ruff check <changed files>` **and** `uv run ruff format .` before every commit. Fix violations even where this plan's own snippets contain them (unused imports, redundant quoted annotations under `from __future__ import annotations`, lines over 100 chars).
- **Never change a rule's `level` in `rules/*.yaml` to make a test pass.** Changing `automation` or `validation.tool` is permitted **only** in Task 11, and only per the verdict table in that task.
- `tests/fixtures/` stays excluded from this repo's ruff/mypy/pytest collection.
- Conventional Commits. Every commit message ends with:
  ```
  Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
  Claude-Session: https://claude.ai/code/session_01FDuHHBinG6kz3tUTfUcPyK
  ```
- Tests land in the same commit as the code they cover.
- The `.arch-standard` stamp shape is **fixed by spec §16.3** and is exactly two keys, `standard-version` and `template-version`. Do not add, rename, or remove a key.

---

## File Structure

```text
pyproject.toml                                   # MODIFY: wheel packaging for the catalog
src/arch_standard/
├── rules/
│   ├── _catalog/                                # CREATE (moved from repo-root rules/)
│   │   ├── application.yaml                     # MOVE
│   │   ├── cross_cutting.yaml                   # MOVE
│   │   ├── dependencies.yaml                    # MOVE
│   │   ├── model_integrity.yaml                 # MOVE
│   │   ├── progressive_structure.yaml           # MOVE
│   │   ├── structure.yaml                       # MOVE
│   │   ├── testing.yaml                         # MOVE
│   │   └── .released/0.1.0/*.yaml               # MOVE
│   ├── catalog.py                               # MODIFY: strict load + packaged_rules_dir()
│   └── model.py                                 # unchanged
├── checks/
│   ├── base.py                                  # MODIFY: Outcome.ERROR / NOT_AUTOMATED, scanned-nothing helper
│   ├── import_contracts.py                      # MODIFY: rule attribution + 5 new contracts
│   ├── ast_rules.py                             # MODIFY: ARCH-033 check
│   └── structure.py                             # MODIFY: ARCH-037 check
├── report.py                                    # MODIFY: full-run completeness, ERROR exit semantics
├── version_stamp.py                             # MODIFY: StampError + guarded parsing
└── cli.py                                       # MODIFY: resources-based rules dir, drift isolation
templates/
├── copier.yml                                   # MODIFY: dependency_source prompt, no CHANGE_ME default
└── pyproject.toml.jinja                         # MODIFY: source-agnostic dependency rendering
tests/
├── rules/test_catalog_loading.py                # CREATE: strict-load semantics
├── rules/test_machine_backed_honesty.py         # CREATE: the meta-test
├── test_packaged_catalog.py                     # CREATE: installed-wheel catalog resolution
├── test_outcome_semantics.py                    # CREATE: PASS/FAIL/SKIP/ERROR/NOT_AUTOMATED
├── test_empty_scan_safety.py                    # CREATE: the four false-green scenarios
├── test_report_completeness.py                  # CREATE: full run covers every catalog rule
├── test_version_stamp.py                        # MODIFY: malformed-stamp cases
├── checks/test_import_contracts.py              # MODIFY: new contract coverage
├── checks/test_structure.py                     # MODIFY: ARCH-037
├── checks/test_ast_rules.py                     # MODIFY: ARCH-033
└── templates/test_distribution_e2e.py           # CREATE: subprocess distribution gate
.github/workflows/ci.yml                         # MODIFY: dogfooding + release-check
Makefile                                         # MODIFY: e2e + selfcheck targets
```

---

## Critical architectural questions — reasoned answers

These were required before finalising the plan. Each answer is load-bearing for the task breakdown.

**Q1. Must `arch-commons` be published before the v0.1.0 generated-project E2E test can pass?**
**No.** This is the key unlock for Task 14. The E2E test builds both wheels locally (`uv build` for the root, `uv build --package arch-commons`) into a temp dist directory and installs from it with `UV_FIND_LINKS` pointing there. That crosses the real distribution boundary — built artifact, clean venv, no monorepo on `sys.path` — without a package index or a git remote. Publishing becomes a separate, human-gated step (Task 13's decision D3) rather than a prerequisite for proving the machinery works. Requiring publication first would make the test un-runnable in CI on a fork or a pre-release branch.

**Q2. Should `arch-standard` depend on a released `arch-commons`, or a workspace/path dependency during development?**
**Neither at runtime — it must stay a dev-only dependency.** Verified: `pyproject.toml:6-10` lists exactly `pydantic`, `pyyaml`, `import-linter` as runtime dependencies, and `arch-commons` appears only in `[dependency-groups] dev`. The validator never imports `commons`; it only probes for it with `importlib.util.find_spec` (`import_contracts.py:47,178`). A runtime dependency would be wrong — it would force every consuming project to install the shared kernel just to lint. Keep the workspace source for dev; add no runtime dependency. **However**, Task 12 must fix the crash this probing causes: `find_spec("commons.types")` raises `ModuleNotFoundError` when the parent package is absent rather than returning `None`.

**Q3. How should `.arch-standard` identify the standard version without introducing undocumented metadata?**
It already does, and the audit was too harsh here: spec §16.3 defines the stamp **verbatim** as exactly `standard-version` and `template-version`. `template-version` is documented in the spec — it is only undocumented in the *error path*, because `read_stamp` raises a bare `KeyError` naming it. So the fix is **guarding, not redesign**: keep both keys, keep the shape frozen, and make every failure mode produce a typed, actionable error. Do not add a schema-version key, do not collapse the two keys.

**Q4. How should the validator represent rules that are prose-only?**
With a **fifth outcome, `NOT_AUTOMATED`** — not with `SKIP`. The audit's central finding is that `SKIP` currently conflates "not applicable to this project" with "we never built this check", and the user's brief is explicit that `SKIP` must not hide "not implemented". `NOT_AUTOMATED` is a permanent property of the *rule* (derived from `validation.tool == "review"`), whereas `SKIP` is a property of *this run against this project*. It never affects the exit code, and it renders in a separate block so a reader can see at a glance how much of the standard is human-reviewed. This is what makes the honesty claim structural rather than documentary.

**Q5. Is changing any of the 14 machine-backed rules actually necessary for v1?**
**Changing all 14 is not necessary; making all 14 honest is.** There are two honest resolutions — implement, or relabel — and the choice per rule should follow one principle: *implement when the rule's substance is an import-graph or filesystem fact the existing builders already model; relabel when the substance requires judgment.* Applying that line yields 11 implemented (of which 4 are pure attribution to contracts that already run) and 3 relabelled. Two of the 14 (ARCH-008, ARCH-033) are `tier: core`, and spec §9 says core rules are "binding from day one, all machine-checkable" — those two are non-negotiable implementations. Full verdict table in Task 11.

**Q6. What exactly constitutes a successful `v0.1.0` release?**
Defined as section G's acceptance gate: the wheel contains the catalog; a clean-venv install can load 53 rules; a generated project installs and passes its own gates plus `arch-standard check --core`; `release-check` passes against the `0.1.0` snapshot; the meta-test proves no rule claims unimplemented automation; and the four false-green scenarios all produce non-zero exits. Tagging and pushing are **manual human steps** (D3) — this plan makes the artifact releasable, it does not perform the release.

---

## Task Breakdown

### Task 1: Catalog load fails loudly

**Files:**
- Modify: `src/arch_standard/rules/catalog.py:21-37`
- Test: `tests/rules/test_catalog_loading.py` (create)

**Interfaces:**
- Produces: `CatalogError` raised by `Catalog.load` on a missing directory, an existing-but-empty directory, or a directory whose YAML yields zero rules. `CatalogError` already exists at `catalog.py:12`.

Do this first: it converts the silent-empty-catalog bug into a loud failure, which is what makes Task 2's regression test meaningful rather than vacuous.

- [ ] **Step 1: Write the failing test**

```python
# tests/rules/test_catalog_loading.py
from __future__ import annotations

from pathlib import Path

import pytest

from arch_standard.rules.catalog import Catalog, CatalogError


def test_given_a_missing_rules_dir__when_loading__then_raises(tmp_path: Path) -> None:
    with pytest.raises(CatalogError, match="does not exist"):
        Catalog.load(tmp_path / "nope")


def test_given_an_empty_rules_dir__when_loading__then_raises(tmp_path: Path) -> None:
    (tmp_path / "rules").mkdir()
    with pytest.raises(CatalogError, match="no rule files"):
        Catalog.load(tmp_path / "rules")


def test_given_yaml_with_no_rules__when_loading__then_raises(tmp_path: Path) -> None:
    rules = tmp_path / "rules"
    rules.mkdir()
    (rules / "empty.yaml").write_text("rules: []\n", encoding="utf-8")
    with pytest.raises(CatalogError, match="zero rules"):
        Catalog.load(rules)


def test_given_the_real_catalog__when_loading__then_all_rules_load() -> None:
    """Guards against the strict checks above rejecting the genuine catalog."""
    catalog = Catalog.load(Path("rules").resolve())
    assert len(catalog) == 53
```

The fourth test uses the repo-root `rules/` path because Task 2 has not moved the catalog yet. Task 2 updates it to `packaged_rules_dir()`.

- [ ] **Step 2: Run to verify failure**

Run: `uv run pytest tests/rules/test_catalog_loading.py -v`
Expected: all three FAIL — currently `Catalog.load` returns an empty catalog without raising.

- [ ] **Step 3: Implement strict loading**

```python
# src/arch_standard/rules/catalog.py — replace the body of Catalog.load
    @classmethod
    def load(cls, rules_dir: Path) -> Catalog:
        if not rules_dir.is_dir():
            raise CatalogError(f"rule catalog directory does not exist: {rules_dir}")
        paths = sorted(rules_dir.glob("*.yaml"))
        if not paths:
            raise CatalogError(f"rule catalog directory contains no rule files: {rules_dir}")
        rules: list[Rule] = []
        seen: dict[str, Path] = {}
        for path in paths:
            raw: Any = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
            for entry in raw.get("rules", []):
                rule = Rule.model_validate(entry)
                if rule.id in seen:
                    raise CatalogError(
                        f"duplicate rule {rule.id} in {path.name} and {seen[rule.id].name}"
                    )
                seen[rule.id] = path
                rules.append(rule)
        if not rules:
            raise CatalogError(f"rule catalog loaded zero rules from {rules_dir}")
        catalog = cls(rules)
        catalog._check_related()
        return catalog
```

- [ ] **Step 4: Run the full suite**

Run: `uv run pytest`
Expected: the three new tests PASS. If any existing test relied on loading an empty directory, fix the *test* to construct a real catalog — do not weaken the guard.

- [ ] **Step 5: Commit**

```bash
git add src/arch_standard/rules/catalog.py tests/rules/test_catalog_loading.py
git commit -m "fix: Catalog.load raises instead of silently returning an empty catalog"
```

**Acceptance criteria:** `Catalog.load` raises `CatalogError` for missing dir, empty dir, and zero-rule content. Full suite green.

**Dependencies:** none. Start here.

---

### Task 2: Package the rule catalog and resolve it with `importlib.resources`

**Files:**
- Move: `rules/*.yaml` → `src/arch_standard/rules/_catalog/*.yaml`
- Move: `rules/.released/` → `src/arch_standard/rules/_catalog/.released/`
- Modify: `pyproject.toml` (wheel packaging + ruff/mypy excludes if needed)
- Modify: `src/arch_standard/rules/catalog.py` (add `packaged_rules_dir`)
- Modify: `src/arch_standard/cli.py:17,71` and `src/arch_standard/docgen.py:9` (drop `_PACKAGED_RULES` traversal)
- Modify: `src/arch_standard/release/snapshot.py` (snapshot root follows the move)
- Test: `tests/test_packaged_catalog.py` (create), `tests/rules/test_catalog_loading.py` (extend)

**Interfaces:**
- Produces: `arch_standard.rules.catalog.packaged_rules_dir() -> Path` — the catalog directory that ships inside the installed package. All callers use this; nobody computes a path from `__file__` parents.

> **Design note (decision D1, already taken):** the YAML physically moves *inside* the package rather than staying at the repo root with a `force-include` build hook. A `force-include` only populates the built wheel, so a source checkout and an installed wheel would resolve differently — exactly the class of bug this task exists to kill. Moving makes both identical with no fallback branch. The repo-root `rules/` directory disappears; authors edit `src/arch_standard/rules/_catalog/`. `_run_check`'s *project-local* override (`root / "rules"` when the target project ships its own catalog, `cli.py:71`) is unrelated and stays.

- [ ] **Step 1: Move the catalog with git**

```bash
mkdir -p src/arch_standard/rules/_catalog
git mv rules/application.yaml rules/cross_cutting.yaml rules/dependencies.yaml \
       rules/model_integrity.yaml rules/progressive_structure.yaml \
       rules/structure.yaml rules/testing.yaml src/arch_standard/rules/_catalog/
git mv rules/.released src/arch_standard/rules/_catalog/.released
rmdir rules
```

- [ ] **Step 2: Write the failing test**

```python
# tests/test_packaged_catalog.py
from __future__ import annotations

import subprocess
import sys
import venv
from pathlib import Path

from arch_standard.rules.catalog import Catalog, packaged_rules_dir


def test_given_the_installed_package__when_locating_rules__then_dir_is_inside_the_package() -> None:
    rules_dir = packaged_rules_dir()
    assert rules_dir.is_dir()
    assert rules_dir.name == "_catalog"
    assert (rules_dir / "structure.yaml").is_file()
    assert Path(Catalog.__module__.replace(".", "/")).name  # sanity: import path intact


def test_given_the_packaged_dir__when_loading__then_the_whole_catalog_loads() -> None:
    assert len(Catalog.load(packaged_rules_dir())) == 53


def test_given_a_built_wheel__when_installed_clean__then_it_ships_and_loads_the_catalog(
    tmp_path: Path,
) -> None:
    """The regression test for the v1 audit's headline finding."""
    repo = Path(__file__).resolve().parents[1]
    dist = tmp_path / "dist"
    subprocess.run(
        ["uv", "build", "--out-dir", str(dist)], cwd=repo, check=True, capture_output=True
    )
    wheels = list(dist.glob("arch_standard-*.whl"))
    assert len(wheels) == 1, f"expected exactly one wheel, got {wheels}"

    env_dir = tmp_path / "venv"
    venv.create(env_dir, with_pip=True)
    python = env_dir / ("Scripts/python.exe" if sys.platform == "win32" else "bin/python")
    subprocess.run([str(python), "-m", "pip", "install", "-q", str(wheels[0])], check=True)

    probe = (
        "from arch_standard.rules.catalog import Catalog, packaged_rules_dir; "
        "print(len(Catalog.load(packaged_rules_dir())))"
    )
    done = subprocess.run(
        [str(python), "-c", probe], check=True, capture_output=True, text=True
    )
    assert done.stdout.strip() == "53"
```

- [ ] **Step 3: Run to verify failure**

Run: `uv run pytest tests/test_packaged_catalog.py -v`
Expected: FAIL — `packaged_rules_dir` does not exist.

- [ ] **Step 4: Implement the resolver**

```python
# src/arch_standard/rules/catalog.py — add near the top, after the imports
from importlib import resources

_CATALOG_PACKAGE = "arch_standard.rules"
_CATALOG_DIRNAME = "_catalog"


def packaged_rules_dir() -> Path:
    """The rule catalog that ships inside this package.

    Resolved through ``importlib.resources`` so a source checkout and an
    installed wheel behave identically. The catalog lives inside the package
    precisely so there is no build-time-only copy step to diverge from.
    """
    return Path(str(resources.files(_CATALOG_PACKAGE).joinpath(_CATALOG_DIRNAME)))
```

- [ ] **Step 5: Point every caller at it**

In `src/arch_standard/cli.py`: delete the `_PACKAGED_RULES = Path(__file__).resolve().parents[2] / "rules"` line, import `packaged_rules_dir`, and replace both uses (`_run_check`'s fallback at `cli.py:71` and the `docs` subcommand). In `src/arch_standard/docgen.py:9`: same. In `src/arch_standard/release/snapshot.py`: the snapshot root becomes `packaged_rules_dir() / ".released"`. Grep to be sure nothing is missed:

```bash
grep -rn "parents\[2\]\|_PACKAGED_RULES" src/ tests/ Makefile .github/
```

Expected after the edit: no hits in `src/`.

- [ ] **Step 6: Make hatchling ship the YAML**

```toml
# pyproject.toml — replace the wheel target block
[tool.hatch.build.targets.wheel]
packages = ["src/arch_standard"]
# The catalog is package data. `.released/` is a dotted dir, which hatchling
# excludes by default, so include it explicitly.
artifacts = ["src/arch_standard/rules/_catalog/.released/**/*.yaml"]
```

- [ ] **Step 7: Run the full suite plus a real build**

Run: `uv run pytest && uv run arch-standard docs --check && uv run arch-standard check tests/fixtures/good_project`
Expected: all green. Then verify the wheel by hand:

```bash
uv build --out-dir /tmp/distcheck
python -c "import zipfile,glob; n=zipfile.ZipFile(glob.glob('/tmp/distcheck/*.whl')[0]).namelist(); print(len([x for x in n if x.endswith('.yaml')]))"
```

Expected: a count of at least 14 (7 catalog files + 7 snapshot files).

- [ ] **Step 8: Commit**

```bash
git add -A
git commit -m "fix: ship the rule catalog in the wheel and resolve it via importlib.resources"
```

**Acceptance criteria:** `uv build` produces a wheel containing the catalog YAML; a clean-venv install loads 53 rules; no `parents[2]` traversal remains in `src/`; `docs --check` still reports the committed document current.

**Dependencies:** Task 1 (strict loading makes the wheel test meaningful — without it the clean-venv probe would print `0` instead of raising).

---

### Task 3: Add `ERROR` and `NOT_AUTOMATED` outcomes

**Files:**
- Modify: `src/arch_standard/checks/base.py:22-37`
- Modify: `src/arch_standard/report.py:47-84`
- Test: `tests/test_outcome_semantics.py` (create)

**Interfaces:**
- Produces: `Outcome.ERROR` (validation could not be performed — always non-zero exit, regardless of rule level) and `Outcome.NOT_AUTOMATED` (the rule is prose-only by declaration — never affects exit code). `Report.exit_code` returns `1` for any `FAIL` on a MUST-family rule **or** any `ERROR` on any rule.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_outcome_semantics.py
from __future__ import annotations

from arch_standard.checks.base import CheckReport, Outcome
from arch_standard.report import Report
from arch_standard.rules.catalog import Catalog, packaged_rules_dir


def _catalog() -> Catalog:
    return Catalog.load(packaged_rules_dir())


def test_given_an_error_outcome__when_computing_exit_code__then_non_zero() -> None:
    report = Report(reports=(CheckReport(rule_id="ARCH-040", outcome=Outcome.ERROR),))
    assert report.exit_code(_catalog()) == 1


def test_given_an_error_on_a_should_rule__when_computing_exit_code__then_still_non_zero() -> None:
    """ERROR is about the validator, not the rule's severity."""
    report = Report(reports=(CheckReport(rule_id="ARCH-013", outcome=Outcome.ERROR),))
    assert report.exit_code(_catalog()) == 1


def test_given_not_automated__when_computing_exit_code__then_zero() -> None:
    report = Report(reports=(CheckReport(rule_id="ARCH-021", outcome=Outcome.NOT_AUTOMATED),))
    assert report.exit_code(_catalog()) == 0


def test_given_mixed_outcomes__when_formatting__then_counts_every_outcome() -> None:
    report = Report(
        reports=(
            CheckReport(rule_id="ARCH-001", outcome=Outcome.PASS),
            CheckReport(rule_id="ARCH-002", outcome=Outcome.SKIP),
            CheckReport(rule_id="ARCH-021", outcome=Outcome.NOT_AUTOMATED),
            CheckReport(rule_id="ARCH-040", outcome=Outcome.ERROR),
        )
    )
    text = report.format_text(_catalog())
    assert "1 passed" in text
    assert "1 skipped" in text
    assert "1 not automated" in text
    assert "1 errored" in text
```

- [ ] **Step 2: Run to verify failure**

Run: `uv run pytest tests/test_outcome_semantics.py -v`
Expected: FAIL — `Outcome.ERROR` does not exist.

- [ ] **Step 3: Extend the enum**

```python
# src/arch_standard/checks/base.py
class Outcome(StrEnum):
    PASS = "PASS"
    FAIL = "FAIL"
    WARN = "WARN"
    SKIP = "SKIP"
    ERROR = "ERROR"
    NOT_AUTOMATED = "N/A"
```

Leave `outcome_for` alone — it maps *findings* to PASS/FAIL/WARN and must not learn about ERROR.

- [ ] **Step 4: Update exit code and formatting**

```python
# src/arch_standard/report.py
    def exit_code(self, catalog: Catalog) -> int:
        must = {r.id for r in catalog.musts()}
        for report in self.reports:
            if report.outcome is Outcome.ERROR:
                return 1
            if report.outcome is Outcome.FAIL and report.rule_id in must:
                return 1
        return 0
```

And in `format_text`, replace the summary line:

```python
        lines.append(
            f"{counts[Outcome.PASS]} passed, {counts[Outcome.FAIL]} failed, "
            f"{counts[Outcome.WARN]} warnings, {counts[Outcome.SKIP]} skipped, "
            f"{counts[Outcome.NOT_AUTOMATED]} not automated, "
            f"{counts[Outcome.ERROR]} errored"
        )
```

- [ ] **Step 5: Run the suite**

Run: `uv run pytest`
Expected: green. Existing tests asserting the old summary string will fail — update those assertions to the new wording.

- [ ] **Step 6: Commit**

```bash
git add src/arch_standard/checks/base.py src/arch_standard/report.py tests/test_outcome_semantics.py
git commit -m "feat: add ERROR and NOT_AUTOMATED outcomes with explicit exit semantics"
```

**Acceptance criteria:** `ERROR` forces exit 1 for any rule level; `NOT_AUTOMATED` never does; the summary line reports all six counts.

**Dependencies:** Task 2 — the test above imports `packaged_rules_dir`, which Task 2 introduces. If you reach this task before Task 2 has landed, substitute `Catalog.load(Path("rules").resolve())` in the helper and convert it when Task 2 lands.

---

### Task 4: The full run reports every catalog rule

**Files:**
- Modify: `src/arch_standard/report.py:18-23`
- Modify: `src/arch_standard/cli.py:76-92` (the `--core` backfill generalises; remove the special case)
- Test: `tests/test_report_completeness.py` (create)

**Interfaces:**
- Consumes: `Outcome.NOT_AUTOMATED` from Task 3.
- Produces: `Report.collect` returns exactly one `CheckReport` per catalog rule. A rule no check claims resolves to `NOT_AUTOMATED` when `validation.tool == "review"`, otherwise `ERROR` (a machine-backed rule with no implementation is a validator defect, not a project result).

The `ERROR` choice here is deliberate and is what makes Task 11's meta-test enforceable at runtime as well as at test time: if anyone ever re-introduces an unimplemented machine-backed rule, every `arch-standard check` run turns red until it is implemented or relabelled.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_report_completeness.py
from __future__ import annotations

from pathlib import Path

from arch_standard.checks import all_checks
from arch_standard.checks.base import Outcome, ProjectLayout
from arch_standard.report import Report
from arch_standard.rules.catalog import Catalog, packaged_rules_dir


def test_given_any_project__when_collecting__then_every_catalog_rule_is_reported() -> None:
    catalog = Catalog.load(packaged_rules_dir())
    layout = ProjectLayout.detect(Path("tests/fixtures/good_project").resolve())
    report = Report.collect(layout, catalog, all_checks())
    reported = {r.rule_id for r in report.reports}
    assert reported == {r.id for r in catalog}, (
        f"unreported: {sorted({r.id for r in catalog} - reported)}"
    )


def test_given_prose_only_rules__when_collecting__then_marked_not_automated() -> None:
    catalog = Catalog.load(packaged_rules_dir())
    layout = ProjectLayout.detect(Path("tests/fixtures/good_project").resolve())
    report = Report.collect(layout, catalog, all_checks())
    by_id = {r.rule_id: r for r in report.reports}
    # ARCH-021 is declared validation.tool == "review" in the catalog.
    assert by_id["ARCH-021"].outcome is Outcome.NOT_AUTOMATED


def test_given_no_duplicate_rows__when_collecting__then_one_row_per_rule() -> None:
    catalog = Catalog.load(packaged_rules_dir())
    layout = ProjectLayout.detect(Path("tests/fixtures/good_project").resolve())
    report = Report.collect(layout, catalog, all_checks())
    ids = [r.rule_id for r in report.reports]
    assert len(ids) == len(set(ids))
```

- [ ] **Step 2: Run to verify failure**

Run: `uv run pytest tests/test_report_completeness.py -v`
Expected: FAIL — 26 rules unreported.

- [ ] **Step 3: Implement completeness in `Report.collect`**

```python
# src/arch_standard/report.py
    @classmethod
    def collect(cls, project: ProjectLayout, catalog: Catalog, checks: list[Check]) -> Report:
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
            outcome = (
                Outcome.NOT_AUTOMATED
                if rule.validation.tool == "review"
                else Outcome.ERROR
            )
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
```

- [ ] **Step 4: Simplify the `--core` path**

The backfill at `cli.py:79-91` is now redundant — `Report.collect` guarantees completeness before `only()` filters. Delete the `missing`/`present` block and keep only:

```python
    if core:
        core_ids = {r.id for r in catalog.core()}
        report = report.only(core_ids)
        header = f"core rules only ({len(core_ids)})"
```

- [ ] **Step 5: Run the suite**

Run: `uv run pytest`
Expected: the three new tests PASS. `arch-standard check tests/fixtures/good_project` now reports 53 rows and — until Task 11 lands — exits 1 with `ERROR` rows for the 14 offenders. **That is the intended intermediate state.** Update any existing CLI test that asserts an exit code or a row count to expect the new reality; do not soften the ERROR rule to keep them green.

- [ ] **Step 6: Commit**

```bash
git add src/arch_standard/report.py src/arch_standard/cli.py tests/test_report_completeness.py
git commit -m "feat: full run reports every catalog rule, never silently omitting one"
```

**Acceptance criteria:** every run reports exactly 53 rows; prose-only rules render `N/A`; unimplemented machine-backed rules render `ERROR` with a diagnostic naming the declared tool.

**Dependencies:** Task 3.

---

### Task 5: Empty-scan safety — never a false green

**Files:**
- Modify: `src/arch_standard/checks/base.py` (add a shared guard helper)
- Modify: `src/arch_standard/checks/ast_rules.py:309-320`, `banned_symbols.py:74`, `structure.py:168`
- Modify: `src/arch_standard/report.py` (zero-context ERROR)
- Test: `tests/test_empty_scan_safety.py` (create)

**Interfaces:**
- Consumes: `Outcome.ERROR`, `Outcome.SKIP` from Task 3.
- Produces: `ProjectLayout.is_scannable() -> bool` — `True` when `src/` exists and at least one bounded context was detected.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_empty_scan_safety.py
from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def _check(target: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "arch_standard", "check", str(target)],
        capture_output=True,
        text=True,
        check=False,
    )


def test_given_an_empty_directory__when_checked__then_non_zero_and_no_false_pass(
    tmp_path: Path,
) -> None:
    done = _check(tmp_path)
    assert done.returncode != 0
    assert "0 passed" in done.stdout


def test_given_a_wrong_layout__when_checked__then_non_zero(tmp_path: Path) -> None:
    (tmp_path / "lib" / "foo").mkdir(parents=True)
    (tmp_path / "lib" / "foo" / "bar.py").write_text("x = 1\n", encoding="utf-8")
    done = _check(tmp_path)
    assert done.returncode != 0


def test_given_unrelated_files__when_checked__then_non_zero(tmp_path: Path) -> None:
    (tmp_path / "README.md").write_text("# hello\n", encoding="utf-8")
    (tmp_path / "data.csv").write_text("a,b\n1,2\n", encoding="utf-8")
    done = _check(tmp_path)
    assert done.returncode != 0


def test_given_src_with_zero_contexts__when_checked__then_non_zero(tmp_path: Path) -> None:
    (tmp_path / "src" / "utils").mkdir(parents=True)
    (tmp_path / "src" / "utils" / "helpers.py").write_text("x = 1\n", encoding="utf-8")
    done = _check(tmp_path)
    assert done.returncode != 0
    assert "no bounded contexts" in done.stdout.lower()


def test_given_a_real_project__when_checked__then_still_zero() -> None:
    done = _check(Path("tests/fixtures/good_project").resolve())
    assert done.returncode == 0, done.stdout
```

- [ ] **Step 2: Run to verify failure**

Run: `uv run pytest tests/test_empty_scan_safety.py -v`
Expected: the first four FAIL (currently exit 0 with "15 passed"); the last PASSes.

- [ ] **Step 3: Add the scannability guard**

```python
# src/arch_standard/checks/base.py — method on ProjectLayout
    def is_scannable(self) -> bool:
        """True when there is actually something for a check to look at.

        A check that scans zero files has not verified anything, so it must
        report SKIP rather than a vacuous PASS.
        """
        return self.src.is_dir() and bool(self.contexts)
```

- [ ] **Step 4: Make the scanning checks honest**

In `AstRulesCheck.run`, `BannedSymbolsCheck.run` and `StructureCheck.run`, add the same early return as the first statement of each:

```python
        if not project.is_scannable():
            return [CheckReport(rule_id=rid, outcome=Outcome.SKIP) for rid in self.rule_ids]
```

- [ ] **Step 5: Make zero contexts an ERROR at the report level**

```python
# src/arch_standard/report.py — inside collect, before the per-check loop
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
```

- [ ] **Step 6: Run the suite**

Run: `uv run pytest`
Expected: all five new tests PASS.

- [ ] **Step 7: Commit**

```bash
git add -A
git commit -m "fix: a project the validator cannot see is an error, not a pass"
```

**Acceptance criteria:** all four false-green scenarios exit non-zero with a diagnostic; `good_project` still exits 0.

**Dependencies:** Tasks 3, 4.

---

### Task 6: Attribute the four already-enforced rules

**Files:**
- Modify: `src/arch_standard/checks/import_contracts.py:22,202-208,278-288`
- Test: `tests/checks/test_import_contracts.py` (extend)

**Interfaces:**
- Produces: `ARCH-007`, `ARCH-008` covered by the per-module layers contract; `ARCH-013`, `ARCH-025` covered by the independence contract. `ImportContractsCheck.rule_ids` grows to 13 entries.

These four rules describe import facts the existing contracts **already enforce** — they are simply not named, so `_parse_broken_rules` (which extracts rule IDs from the contract *name*) never attributes them. ARCH-008's "domain and application import only abstractions, never adapters" is exactly the layers contract; ARCH-007's "application does not construct concrete adapters" is unreachable once application cannot import infrastructure; ARCH-025's "zero imports between contexts" is exactly the independence contract; ARCH-013's "no cycles between contexts" is strictly implied by that same independence contract.

- [ ] **Step 1: Write the failing test**

```python
# tests/checks/test_import_contracts.py — append
def test_given_a_modular_project__when_building__then_layer_contract_names_arch_007_and_008() -> None:
    layout = ProjectLayout.detect(Path("tests/fixtures/modular_project").resolve())
    ini = build_contracts(layout)
    assert "ARCH-007" in ini
    assert "ARCH-008" in ini


def test_given_contexts__when_building__then_independence_names_arch_013_and_025() -> None:
    layout = ProjectLayout.detect(Path("tests/fixtures/modular_project").resolve())
    ini = build_contracts(layout)
    independence = [b for b in ini.split("[importlinter:contract:") if b.startswith("ARCH-012")]
    assert independence, "independence contract missing"
    assert "ARCH-013" in independence[0]
    assert "ARCH-025" in independence[0]


def test_given_the_check__when_listing_rules__then_attributed_rules_are_claimed() -> None:
    for rid in ("ARCH-007", "ARCH-008", "ARCH-013", "ARCH-025"):
        assert rid in ImportContractsCheck.rule_ids
```

- [ ] **Step 2: Run to verify failure**

Run: `uv run pytest tests/checks/test_import_contracts.py -v -k "arch_007 or arch_013 or attributed"`
Expected: FAIL.

- [ ] **Step 3: Name the rules on the contracts**

```python
# src/arch_standard/checks/import_contracts.py
# ARCH-007/008 ride the layers contract: once application cannot import
# infrastructure, it cannot name an adapter class to construct one (007), and
# domain/application are left importing only the abstractions (008).
_MODULE_LAYER_RULES: tuple[str, ...] = (
    "ARCH-001",
    "ARCH-002",
    "ARCH-005",
    "ARCH-007",
    "ARCH-008",
)
```

and in `build_contracts`, rename the independence contract:

```python
            "[importlinter:contract:ARCH-012]",
            "name = ARCH-012 ARCH-013 ARCH-025 bounded-context independence",
```

then extend the claimed set:

```python
    rule_ids: tuple[str, ...] = (
        "ARCH-001",
        "ARCH-002",
        "ARCH-005",
        "ARCH-006",
        "ARCH-007",
        "ARCH-008",
        "ARCH-012",
        "ARCH-013",
        "ARCH-025",
        "ARCH-034",
        "ARCH-035",
        "ARCH-046",
        "ARCH-052",
    )
```

- [ ] **Step 4: Verify against the violation fixture**

Run: `uv run pytest && uv run arch-standard check tests/fixtures/bad_project`
Expected: `bad_project` now reports ARCH-007 and ARCH-008 as FAIL alongside ARCH-001/002/005 (it violates the layers contract), proving attribution actually fires rather than vacuously passing.

- [ ] **Step 5: Commit**

```bash
git add src/arch_standard/checks/import_contracts.py tests/checks/test_import_contracts.py
git commit -m "feat: attribute ARCH-007/008/013/025 to the contracts that already enforce them"
```

**Acceptance criteria:** the four rules appear in contract names, are claimed by `rule_ids`, and FAIL on `bad_project` where the underlying contract breaks.

**Dependencies:** none (independent of Tasks 3–5), but must land before Task 11.

---

### Task 7: Five new import contracts (ARCH-009, 011, 014, 015, 017)

**Files:**
- Modify: `src/arch_standard/checks/import_contracts.py`
- Test: `tests/checks/test_import_contracts.py` (extend)

**Interfaces:**
- Consumes: `_roots`, `_commons_types_importable`, `_module_contracts` from the existing module.
- Produces: `ImportContractsCheck.rule_ids` grows to 18. New helper `_shared_kernel_available(project) -> bool`.

Each of these is a direct import-graph fact the existing builder already models; none needs new tooling.

- [ ] **Step 1: Write the failing tests**

```python
# tests/checks/test_import_contracts.py — append
def test_given_a_bootstrap_dir__when_building__then_arch_017_forbids_importing_it(
    tmp_path: Path,
) -> None:
    src = tmp_path / "src"
    (src / "bootstrap").mkdir(parents=True)
    (src / "sales" / "orders" / "domain").mkdir(parents=True)
    layout = ProjectLayout.detect(tmp_path)
    ini = build_contracts(layout)
    assert "ARCH-017" in ini
    assert "bootstrap" in ini


def test_given_a_shared_kernel__when_building__then_arch_014_contract_is_emitted(
    tmp_path: Path,
) -> None:
    src = tmp_path / "src"
    (src / "shared_kernel").mkdir(parents=True)
    (src / "sales" / "orders" / "domain").mkdir(parents=True)
    layout = ProjectLayout.detect(tmp_path)
    ini = build_contracts(layout)
    assert "ARCH-014" in ini


def test_given_no_shared_kernel__when_building__then_no_arch_014_contract(
    tmp_path: Path,
) -> None:
    src = tmp_path / "src"
    (src / "sales" / "orders" / "domain").mkdir(parents=True)
    layout = ProjectLayout.detect(tmp_path)
    assert "ARCH-014" not in build_contracts(layout)


def test_given_commons_types__when_building__then_arch_015_forbids_contexts() -> None:
    layout = ProjectLayout.detect(Path("tests/fixtures/good_project").resolve())
    ini = build_contracts(layout)
    assert "ARCH-015" in ini


def test_given_entrypoints__when_building__then_arch_009_and_011_contracts_exist() -> None:
    layout = ProjectLayout.detect(Path("tests/fixtures/good_project").resolve())
    ini = build_contracts(layout)
    assert "ARCH-009" in ini
    assert "ARCH-011" in ini
```

- [ ] **Step 2: Run to verify failure**

Run: `uv run pytest tests/checks/test_import_contracts.py -v -k "arch_017 or arch_014 or arch_015 or arch_009"`
Expected: FAIL.

- [ ] **Step 3: Implement the contracts**

Add the `shared_kernel` root alongside `bootstrap` in `_roots`:

```python
def _roots(project: ProjectLayout) -> list[str]:
    return [
        *project.contexts,
        *(["commons"] if _commons_root_available(project) else []),
        *(d for d in ("bootstrap", "shared_kernel") if (project.src / d).is_dir()),
    ]
```

Then append these blocks in `build_contracts`, after the ARCH-012 block:

```python
    if (project.src / "bootstrap").is_dir() and project.contexts:
        lines += [
            "[importlinter:contract:ARCH-017]",
            "name = ARCH-017 nothing imports bootstrap",
            "type = forbidden",
            "source_modules =",
            *(f"    {context}" for context in project.contexts),
            "forbidden_modules =",
            "    bootstrap",
            "",
        ]

    if (project.src / "shared_kernel").is_dir() and project.contexts:
        lines += [
            "[importlinter:contract:ARCH-014]",
            "name = ARCH-014 shared_kernel imports nothing from any context",
            "type = forbidden",
            "source_modules =",
            "    shared_kernel",
            "forbidden_modules =",
            *(f"    {context}" for context in project.contexts),
            "",
        ]

    if _commons_types_importable(project) and project.contexts:
        forbidden_015 = [f"    {context}" for context in project.contexts]
        if (project.src / "shared_kernel").is_dir():
            forbidden_015.append("    shared_kernel")
        lines += [
            "[importlinter:contract:ARCH-015]",
            "name = ARCH-015 commons.types depends on nothing above it",
            "type = forbidden",
            "source_modules =",
            "    commons.types",
            "forbidden_modules =",
            *forbidden_015,
            "",
        ]

    for context in project.contexts:
        if not project.entrypoints_dir(context).is_dir():
            continue
        infra = [
            f"    {context}.{module}.infrastructure"
            for module in project.modules(context)
            if project.module_infrastructure_dir(context, module).is_dir()
        ]
        if infra:
            lines += [
                f"[importlinter:contract:ARCH-009-{context}]",
                f"name = ARCH-009 entrypoints do not touch infrastructure ({context})",
                "type = forbidden",
                "source_modules =",
                f"    {context}.entrypoints",
                "forbidden_modules =",
                *infra,
                "",
            ]
        # ARCH-011: an entrypoint module may not import a sibling entrypoint.
        # providers.py is the sanctioned wiring seam and is exempt.
        siblings = sorted(
            p.stem
            for p in project.entrypoints_dir(context).glob("*.py")
            if p.stem not in ("__init__", "providers")
        )
        if len(siblings) > 1:
            lines += [
                f"[importlinter:contract:ARCH-011-{context}]",
                f"name = ARCH-011 entrypoints do not import each other ({context})",
                "type = forbidden",
                "source_modules =",
                *(f"    {context}.entrypoints.{name}" for name in siblings),
                "forbidden_modules =",
                *(f"    {context}.entrypoints.{name}" for name in siblings),
                "",
            ]
```

> Note on the ARCH-011 self-overlap: import-linter skips source/forbidden pairs where one is the other (or a subpackage of it), so a module is never reported as forbidden from itself. This is the same property the existing ARCH-046 contract already relies on — see the docstring at `_module_contracts`.

Then extend `rule_ids` with `"ARCH-009"`, `"ARCH-011"`, `"ARCH-014"`, `"ARCH-015"`, `"ARCH-017"`.

- [ ] **Step 4: Run the suite and the fixtures**

Run: `uv run pytest && uv run arch-standard check tests/fixtures/good_project && uv run arch-standard check tests/fixtures/modular_project`
Expected: suite green; both fixtures still exit 0 (they do not violate the new contracts).

- [ ] **Step 5: Prove each new contract can actually fail**

Add one negative test per new rule — build a tmp project that genuinely violates it and assert the rule reports FAIL. Without this, a contract that is emitted but never fires is indistinguishable from one that works. Example for ARCH-017:

```python
def test_given_a_context_importing_bootstrap__when_checked__then_arch_017_fails(
    tmp_path: Path,
) -> None:
    src = tmp_path / "src"
    (src / "bootstrap").mkdir(parents=True)
    (src / "bootstrap" / "__init__.py").write_text("container = 1\n", encoding="utf-8")
    app = src / "sales" / "orders" / "application"
    app.mkdir(parents=True)
    (src / "sales" / "__init__.py").write_text("", encoding="utf-8")
    (src / "sales" / "orders" / "__init__.py").write_text("", encoding="utf-8")
    (app / "__init__.py").write_text("", encoding="utf-8")
    (app / "svc.py").write_text("from bootstrap import container\n", encoding="utf-8")
    (src / "sales" / "orders" / "domain").mkdir(parents=True)
    (src / "sales" / "orders" / "domain" / "__init__.py").write_text("", encoding="utf-8")

    layout = ProjectLayout.detect(tmp_path)
    catalog = Catalog.load(packaged_rules_dir())
    reports = {r.rule_id: r for r in ImportContractsCheck().run(layout, catalog)}
    assert reports["ARCH-017"].outcome is Outcome.FAIL
```

Write the equivalent for ARCH-009, ARCH-011, ARCH-014 and ARCH-015.

- [ ] **Step 6: Commit**

```bash
git add src/arch_standard/checks/import_contracts.py tests/checks/test_import_contracts.py
git commit -m "feat: enforce ARCH-009/011/014/015/017 with real import contracts"
```

**Acceptance criteria:** five new contracts emit only when applicable, are claimed by `rule_ids`, and each has a negative test proving it FAILs on a genuine violation.

**Dependencies:** Task 6 (same file — sequential to avoid conflicts).

---

### Task 8: ARCH-037 — providers.py presence

**Files:**
- Modify: `src/arch_standard/checks/structure.py:168`
- Test: `tests/checks/test_structure.py` (extend)

**Interfaces:**
- Produces: `StructureCheck.rule_ids` grows to `("ARCH-037", "ARCH-047", "ARCH-048", "ARCH-051")`.

Only the structural half of ARCH-037 is machine-checkable here: *a context that exposes entrypoints must have `entrypoints/providers.py`*. The second half ("entrypoints import services only from providers") is the ARCH-009/011 contract family from Task 7.

- [ ] **Step 1: Write the failing test**

```python
# tests/checks/test_structure.py — append
def test_given_entrypoints_without_providers__when_checked__then_arch_037_fails(
    tmp_path: Path,
) -> None:
    src = tmp_path / "src" / "sales"
    (src / "entrypoints").mkdir(parents=True)
    (src / "entrypoints" / "http.py").write_text("handler = 1\n", encoding="utf-8")
    (src / "orders" / "domain").mkdir(parents=True)
    layout = ProjectLayout.detect(tmp_path)
    catalog = Catalog.load(packaged_rules_dir())
    reports = {r.rule_id: r for r in StructureCheck().run(layout, catalog)}
    assert reports["ARCH-037"].outcome is Outcome.FAIL


def test_given_entrypoints_with_providers__when_checked__then_arch_037_passes(
    tmp_path: Path,
) -> None:
    src = tmp_path / "src" / "sales"
    (src / "entrypoints").mkdir(parents=True)
    (src / "entrypoints" / "providers.py").write_text("svc = 1\n", encoding="utf-8")
    (src / "orders" / "domain").mkdir(parents=True)
    layout = ProjectLayout.detect(tmp_path)
    catalog = Catalog.load(packaged_rules_dir())
    reports = {r.rule_id: r for r in StructureCheck().run(layout, catalog)}
    assert reports["ARCH-037"].outcome is Outcome.PASS


def test_given_no_entrypoints__when_checked__then_arch_037_skips(tmp_path: Path) -> None:
    src = tmp_path / "src" / "sales" / "orders" / "domain"
    src.mkdir(parents=True)
    layout = ProjectLayout.detect(tmp_path)
    catalog = Catalog.load(packaged_rules_dir())
    reports = {r.rule_id: r for r in StructureCheck().run(layout, catalog)}
    assert reports["ARCH-037"].outcome is Outcome.SKIP
```

- [ ] **Step 2: Run to verify failure**

Run: `uv run pytest tests/checks/test_structure.py -v -k arch_037`
Expected: FAIL — `KeyError: 'ARCH-037'`.

- [ ] **Step 3: Implement**

```python
# src/arch_standard/checks/structure.py — inside StructureCheck.run
    def _arch_037(self, project: ProjectLayout) -> tuple[Outcome, tuple[Finding, ...]]:
        """A context exposing entrypoints must route wiring through providers.py."""
        contexts = [c for c in project.contexts if project.entrypoints_dir(c).is_dir()]
        if not contexts:
            return Outcome.SKIP, ()
        findings = tuple(
            Finding(
                rule_id="ARCH-037",
                path=str(project.entrypoints_dir(context)),
                line=None,
                message=f"{context}/entrypoints/ has no providers.py",
            )
            for context in contexts
            if not (project.entrypoints_dir(context) / "providers.py").is_file()
        )
        return outcome_for(Level.MUST, bool(findings)), findings
```

Wire it into `run` alongside the existing rules and add `"ARCH-037"` to `rule_ids`. `structure.py` already imports `Finding`, `CheckReport`, `ProjectLayout` and `outcome_for` from `checks.base`; add `Outcome` and `Level` to that same import block (`Level` comes from `arch_standard.rules.model`).

- [ ] **Step 4: Run the suite**

Run: `uv run pytest && uv run arch-standard check tests/fixtures/good_project`
Expected: green; `good_project` has `sales/entrypoints/` — if it lacks `providers.py`, **add it to the fixture** (that is a genuine fixture gap, not a rule to weaken).

- [ ] **Step 5: Commit**

```bash
git add src/arch_standard/checks/structure.py tests/checks/test_structure.py tests/fixtures/
git commit -m "feat: enforce ARCH-037 (per-context entrypoints/providers.py)"
```

**Acceptance criteria:** ARCH-037 FAILs without `providers.py`, PASSes with it, SKIPs when the context has no entrypoints.

**Dependencies:** none beyond Task 3 (needs `Outcome.SKIP` semantics); parallelisable with Tasks 6–7.

---

### Task 9: ARCH-033 — every use-case write goes through a Unit of Work (core)

**Files:**
- Modify: `src/arch_standard/checks/ast_rules.py`
- Test: `tests/checks/test_ast_rules.py` (extend)

**Interfaces:**
- Produces: `_IMPLEMENTED["ARCH-033"]`; `AstRulesCheck.rule_ids` grows to include `"ARCH-033"`.

This is `tier: core` and spec §9 requires core rules to be machine-checkable, so it is non-negotiable. The heuristic must be **narrow and documented**: flag an application-layer method that calls `.commit()` on a receiver that is not the object bound by an enclosing `with` statement. That catches the catalog's own `incorrect` example (`self._orders.session.commit()`) without trying to infer "does this method change state", which is not decidable from the AST.

- [ ] **Step 1: Write the failing test**

```python
# tests/checks/test_ast_rules.py — append
def _app_module(tmp_path: Path, body: str) -> ProjectLayout:
    app = tmp_path / "src" / "sales" / "orders" / "application"
    app.mkdir(parents=True)
    (tmp_path / "src" / "sales" / "orders" / "domain").mkdir(parents=True)
    (app / "order_service.py").write_text(body, encoding="utf-8")
    return ProjectLayout.detect(tmp_path)


def test_given_a_direct_session_commit__when_checked__then_arch_033_fails(
    tmp_path: Path,
) -> None:
    layout = _app_module(
        tmp_path,
        "class OrderService:\n"
        "    def cancel(self, cmd):\n"
        "        order = self._orders.get(cmd.id)\n"
        "        self._orders.session.commit()\n",
    )
    catalog = Catalog.load(packaged_rules_dir())
    reports = {r.rule_id: r for r in AstRulesCheck().run(layout, catalog)}
    assert reports["ARCH-033"].outcome is Outcome.FAIL


def test_given_a_uow_block__when_checked__then_arch_033_passes(tmp_path: Path) -> None:
    layout = _app_module(
        tmp_path,
        "class OrderService:\n"
        "    def cancel(self, cmd):\n"
        "        with self._uow as uow:\n"
        "            order = self._orders.get(cmd.id)\n"
        "            uow.commit()\n",
    )
    catalog = Catalog.load(packaged_rules_dir())
    reports = {r.rule_id: r for r in AstRulesCheck().run(layout, catalog)}
    assert reports["ARCH-033"].outcome is Outcome.PASS


def test_given_no_commit_at_all__when_checked__then_arch_033_passes(tmp_path: Path) -> None:
    layout = _app_module(
        tmp_path,
        "class OrderService:\n    def find(self, cmd):\n        return self._orders.get(cmd.id)\n",
    )
    catalog = Catalog.load(packaged_rules_dir())
    reports = {r.rule_id: r for r in AstRulesCheck().run(layout, catalog)}
    assert reports["ARCH-033"].outcome is Outcome.PASS
```

- [ ] **Step 2: Run to verify failure**

Run: `uv run pytest tests/checks/test_ast_rules.py -v -k arch_033`
Expected: FAIL — `KeyError: 'ARCH-033'`.

- [ ] **Step 3: Implement the check**

```python
# src/arch_standard/checks/ast_rules.py
def _arch_033(project: ProjectLayout) -> list[Finding]:
    """Flag a .commit() whose receiver is not bound by an enclosing `with`.

    Deliberately narrow: deciding "does this method change state" is not
    possible from the AST, so this checks the one determinate signal the rule
    names -- committing through something other than the Unit of Work block.
    """
    findings: list[Finding] = []
    for context, module in project.iter_modules():
        app_dir = project.module_application_dir(context, module)
        if not app_dir.is_dir():
            continue
        for path in sorted(app_dir.rglob("*.py")):
            tree = ast.parse(path.read_text(encoding="utf-8"))
            for func in (
                n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef | ast.AsyncFunctionDef)
            ):
                bound: set[str] = set()
                for with_node in (n for n in ast.walk(func) if isinstance(n, ast.With)):
                    for item in with_node.items:
                        if isinstance(item.optional_vars, ast.Name):
                            bound.add(item.optional_vars.id)
                for call in (n for n in ast.walk(func) if isinstance(n, ast.Call)):
                    fn = call.func
                    if not isinstance(fn, ast.Attribute) or fn.attr != "commit":
                        continue
                    receiver = fn.value
                    if isinstance(receiver, ast.Name) and receiver.id in bound:
                        continue
                    findings.append(
                        Finding(
                            rule_id="ARCH-033",
                            path=str(path),
                            line=call.lineno,
                            message=(
                                f"{func.name} commits outside a Unit of Work block; "
                                "open `with self._uow as uow:` and commit through uow"
                            ),
                        )
                    )
    return findings
```

Register it in `_IMPLEMENTED` and add `"ARCH-033"` to `AstRulesCheck.rule_ids`.

- [ ] **Step 4: Run the suite and the fixtures**

Run: `uv run pytest && uv run arch-standard check tests/fixtures/bad_project`
Expected: suite green. `bad_project`'s `order_service.py` should now report ARCH-033 FAIL if it commits directly — if it does not currently contain such a call, **add one to the fixture**, since a violation fixture that does not violate the rule proves nothing.

- [ ] **Step 5: Commit**

```bash
git add src/arch_standard/checks/ast_rules.py tests/checks/test_ast_rules.py tests/fixtures/
git commit -m "feat: enforce ARCH-033 (writes commit through the Unit of Work)"
```

**Acceptance criteria:** ARCH-033 FAILs on a direct `session.commit()`, PASSes on a `with uow:` block and on read-only methods; core tier is now 12/12 machine-checked.

**Dependencies:** Task 3; parallelisable with Tasks 6–8.

---

### Task 10: Relabel the three judgment rules and lock honesty with a meta-test

**Files:**
- Modify: `src/arch_standard/rules/_catalog/application.yaml` (ARCH-024, ARCH-042, ARCH-045 — confirm which file each lives in with `grep -rn "ARCH-024" src/arch_standard/rules/_catalog/`)
- Create: `tests/rules/test_machine_backed_honesty.py`
- Modify: `ARCHITECTURE_STANDARD.md` (regenerated, not hand-edited)

**Interfaces:**
- Produces: the invariant *every rule whose `validation.tool` is machine-backed is claimed by some registered check's `rule_ids`*.

**Verdict table for all 14 offenders** — this is the design-sensitive core of the plan. The line applied: *implement when the rule's substance is an import-graph or filesystem fact the existing builders already model; relabel when the substance requires judgment.*

| Rule | Level / Tier | Verdict | Resolution | Landed in |
|---|---|---|---|---|
| ARCH-007 | MUST | **A — attribute** | Unreachable once application cannot import infrastructure; ride the layers contract. `automation: full` → `partial` (direct instantiation within infrastructure is still unchecked). | Task 6 |
| ARCH-008 | MUST **core** | **A — attribute** | Import half *is* the layers contract. `automation: full` → `partial` ("implements a Protocol" is not checked). Core, so non-negotiable. | Task 6 |
| ARCH-009 | MUST | **A — implement** | New forbidden contract `entrypoints -/-> infrastructure`. `tool: ast-checker` → `import-linter`; `automation` stays `partial`. | Task 7 |
| ARCH-011 | MUST | **A — implement** | New forbidden contract between sibling entrypoint modules, `providers` exempt. | Task 7 |
| ARCH-013 | SHOULD | **A — attribute** | Strictly implied by ARCH-012 independence (no context→context import at all ⇒ no cycle). | Task 6 |
| ARCH-014 | MUST | **A — implement** | `shared_kernel` becomes a root package; forbidden contract to every context. | Task 7 |
| ARCH-015 | MUST | **A — implement** | Mirror of the existing ARCH-035 contract, same gating helper. | Task 7 |
| ARCH-017 | MUST | **A — implement** | Forbidden contract `contexts -/-> bootstrap`. | Task 7 |
| ARCH-024 | MUST\* | **B — relabel** | "When it *starts being consumed*" is a judgment about intent; ARCH-043/044 already cover published-schema mechanics. `tool: schema` → `review`, `automation: partial` → `manual`. | this task |
| ARCH-025 | MUST | **A — attribute** | Import half *is* the independence contract. `automation: full` → `partial` (the "declared contract / ACL present" half is unchecked). | Task 6 |
| ARCH-033 | MUST **core** | **A — implement** | Narrow AST check on commit-outside-`with`. Core, so non-negotiable. | Task 9 |
| ARCH-037 | MUST | **A — implement** | Structural: `providers.py` presence per context with entrypoints. `tool: ast-checker` → `schema` is wrong; keep `ast-checker`, `automation: partial`. | Task 8 |
| ARCH-042 | SHOULD | **B — relabel** | "Shared across use-case modules" and the three-homes judgment are not determinable; the 3+ threshold needs cross-module usage analysis well beyond v1. `tool: ast-checker` → `review`, `automation: partial` → `manual`. | this task |
| ARCH-045 | MUST | **B — relabel** | "Carries only the fields and operations it uses" is intent. The import half is already ARCH-012/025. `tool: ast-checker` → `review`, `automation: partial` → `manual`. | this task |

Net: **11 implemented or attributed, 3 relabelled.** Core tier reaches 12/12. Machine-backed MUST coverage rises from 20/38 to 31/38, with the remaining 7 honestly declared `review`.

- [ ] **Step 1: Write the meta-test**

```python
# tests/rules/test_machine_backed_honesty.py
from __future__ import annotations

from arch_standard.checks import all_checks
from arch_standard.rules.catalog import Catalog, packaged_rules_dir

MACHINE_TOOLS = frozenset({"import-linter", "grimp", "ruff", "ast-checker", "schema"})


def test_given_a_machine_backed_rule__when_scanning_checks__then_some_check_claims_it() -> None:
    """The invariant the v1 audit found violated by 14 rules.

    A rule whose validation.tool names a machine validator is a promise to the
    reader of ARCHITECTURE_STANDARD.md that the rule is automatically enforced.
    Keep that promise structural: if no registered check claims the rule id,
    either build the check or relabel the rule as `review`.
    """
    catalog = Catalog.load(packaged_rules_dir())
    claimed: set[str] = set()
    for check in all_checks():
        claimed |= set(check.rule_ids)
    unbacked = sorted(
        rule.id
        for rule in catalog
        if rule.validation.tool in MACHINE_TOOLS and rule.id not in claimed
    )
    assert not unbacked, (
        "these rules declare a machine validator but no check implements them: "
        f"{unbacked} -- implement the check, or set validation.tool to 'review'"
    )


def test_given_a_core_rule__when_scanning_checks__then_it_is_machine_checked() -> None:
    """Spec 9: core rules are 'binding from day one, all machine-checkable'."""
    catalog = Catalog.load(packaged_rules_dir())
    claimed: set[str] = set()
    for check in all_checks():
        claimed |= set(check.rule_ids)
    unchecked = sorted(r.id for r in catalog.core() if r.id not in claimed)
    assert not unchecked, f"core rules with no check: {unchecked}"


def test_given_a_claimed_rule__when_looked_up__then_it_exists_in_the_catalog() -> None:
    """The inverse: no check may claim a rule id the catalog does not define."""
    catalog = Catalog.load(packaged_rules_dir())
    known = {r.id for r in catalog}
    for check in all_checks():
        for rule_id in check.rule_ids:
            assert rule_id in known, f"{type(check).__name__} claims unknown rule {rule_id}"
```

- [ ] **Step 2: Run to verify failure**

Run: `uv run pytest tests/rules/test_machine_backed_honesty.py -v`
Expected: with Tasks 6–9 landed, the first test FAILs listing exactly `['ARCH-024', 'ARCH-042', 'ARCH-045']`. If it lists anything else, an earlier task is incomplete — stop and fix that first.

- [ ] **Step 3: Apply the three relabels**

For ARCH-024, ARCH-042 and ARCH-045, change only `automation` and `validation.tool` per the verdict table. Example shape:

```yaml
    automation: manual
    ...
    validation:
      tool: review
      detail: reviewed at PR time; not determinable from the import graph or AST
```

Leave `level`, `description`, `rationale`, `correct`, `incorrect` and `related` untouched.

- [ ] **Step 4: Apply the automation downgrades from Task 6's attributions**

ARCH-007, ARCH-008 and ARCH-025 each keep `validation.tool` but move `automation: full` → `automation: partial`, because attribution enforces the import half only. Add a one-line `validation.detail` saying which contract carries it, e.g. `detail: layered contract (import half); Protocol conformance reviewed at PR time`.

- [ ] **Step 5: Regenerate the standard document**

Run: `uv run arch-standard docs`
Then: `uv run arch-standard docs --check`
Expected: `ARCHITECTURE_STANDARD.md is current`. Never hand-edit that file.

- [ ] **Step 6: Run everything**

Run: `uv run pytest && uv run arch-standard check tests/fixtures/good_project`
Expected: the meta-test passes; `good_project` exits 0 with zero `ERROR` rows (Task 4's runtime guard is now satisfied for every rule).

- [ ] **Step 7: Commit**

```bash
git add src/arch_standard/rules/_catalog/ ARCHITECTURE_STANDARD.md tests/rules/test_machine_backed_honesty.py
git commit -m "fix: relabel three judgment rules and lock machine-backed honesty with a meta-test"
```

**Acceptance criteria:** the meta-test passes; core is 12/12; no catalog rule claims a machine validator without a check; `docs --check` clean.

**Dependencies:** Tasks 6, 7, 8, 9 must all be landed. This is the convergence point.

---

### Task 11: `.arch-standard` stamp safety

**Files:**
- Modify: `src/arch_standard/version_stamp.py`
- Modify: `src/arch_standard/cli.py:52-53,95-97`
- Modify: `src/arch_standard/checks/import_contracts.py:47,178` (the `find_spec` crash)
- Test: `tests/test_version_stamp.py` (extend), `tests/test_cli_drift_notice.py` (extend)

**Interfaces:**
- Produces: `StampError(Exception)` in `version_stamp.py`; `read_stamp` raises it for every malformed input; `_drift_notice` never propagates an exception and never influences the exit code.

Behaviour table — derived from spec §16.3 ("It does not fail on drift — upgrading is the project's decision"), so **no stamp condition may produce the exit code of an architecture violation**:

| Condition | Behaviour | Exit code |
|---|---|---|
| no `.arch-standard` file | silent; no notice | unchanged |
| malformed TOML | one-line warning to stderr naming the file and the parse error | unchanged |
| missing `standard-version` or `template-version` | one-line warning naming the missing key | unchanged |
| version not `N.N.N` | one-line warning naming the bad value | unchanged |
| stamp behind the running catalog | existing drift notice | unchanged |
| any unexpected error in the notice path | warning; validation result stands | unchanged |

- [ ] **Step 1: Write the failing test**

```python
# tests/test_version_stamp.py — append
from arch_standard.version_stamp import StampError, read_stamp


def test_given_malformed_toml__when_reading__then_raises_stamp_error(tmp_path: Path) -> None:
    (tmp_path / ".arch-standard").write_text("not toml [[[\n", encoding="utf-8")
    with pytest.raises(StampError, match="not valid TOML"):
        read_stamp(tmp_path)


def test_given_a_missing_key__when_reading__then_raises_naming_the_key(tmp_path: Path) -> None:
    (tmp_path / ".arch-standard").write_text('standard-version = "1.0.0"\n', encoding="utf-8")
    with pytest.raises(StampError, match="template-version"):
        read_stamp(tmp_path)


def test_given_a_non_string_version__when_reading__then_raises(tmp_path: Path) -> None:
    (tmp_path / ".arch-standard").write_text(
        "standard-version = 1\ntemplate-version = \"1.0.0\"\n", encoding="utf-8"
    )
    with pytest.raises(StampError, match="standard-version"):
        read_stamp(tmp_path)


def test_given_a_malformed_version_string__when_reading__then_raises(tmp_path: Path) -> None:
    (tmp_path / ".arch-standard").write_text(
        'standard-version = "one.two"\ntemplate-version = "1.0.0"\n', encoding="utf-8"
    )
    with pytest.raises(StampError, match="one.two"):
        read_stamp(tmp_path)
```

```python
# tests/test_cli_drift_notice.py — append
def test_given_a_broken_stamp__when_checking__then_exit_code_matches_a_clean_run(
    tmp_path: Path,
) -> None:
    """A stamp problem must never look like an architecture violation."""
    import shutil

    good = Path("tests/fixtures/good_project").resolve()
    target = tmp_path / "proj"
    shutil.copytree(good, target)
    clean = subprocess.run(
        [sys.executable, "-m", "arch_standard", "check", str(target)],
        capture_output=True, text=True, check=False,
    )
    (target / ".arch-standard").write_text("garbage [[[\n", encoding="utf-8")
    broken = subprocess.run(
        [sys.executable, "-m", "arch_standard", "check", str(target)],
        capture_output=True, text=True, check=False,
    )
    assert broken.returncode == clean.returncode
    assert "Traceback" not in broken.stderr
    assert ".arch-standard" in (broken.stderr + broken.stdout)
```

- [ ] **Step 2: Run to verify failure**

Run: `uv run pytest tests/test_version_stamp.py tests/test_cli_drift_notice.py -v`
Expected: FAIL — `StampError` does not exist; the CLI test shows a traceback and a differing exit code.

- [ ] **Step 3: Implement guarded parsing**

```python
# src/arch_standard/version_stamp.py
class StampError(Exception):
    """The .arch-standard stamp exists but cannot be interpreted."""


def read_stamp(root: Path) -> VersionStamp | None:
    path = root / _STAMP_FILENAME
    if not path.is_file():
        return None
    try:
        data = tomllib.loads(path.read_text(encoding="utf-8"))
    except tomllib.TOMLDecodeError as exc:
        raise StampError(f"{path} is not valid TOML: {exc}") from exc
    values: dict[str, str] = {}
    for key in ("standard-version", "template-version"):
        if key not in data:
            raise StampError(f"{path} is missing required key {key!r}")
        value = data[key]
        if not isinstance(value, str):
            raise StampError(f"{path}: {key} must be a string, got {type(value).__name__}")
        try:
            parse_semver(value)
        except ValueError as exc:
            raise StampError(f"{path}: {key} is not a valid version: {value!r}") from exc
        values[key] = value
    return VersionStamp(
        standard_version=values["standard-version"],
        template_version=values["template-version"],
    )
```

Make `parse_semver` raise `ValueError` rather than unpacking blindly:

```python
def parse_semver(version: str) -> tuple[int, int, int]:
    parts = version.split(".")
    if len(parts) != 3:
        raise ValueError(f"expected MAJOR.MINOR.PATCH, got {version!r}")
    try:
        major, minor, patch = (int(p) for p in parts)
    except ValueError as exc:
        raise ValueError(f"expected numeric version parts, got {version!r}") from exc
    return major, minor, patch
```

- [ ] **Step 4: Isolate the notice path in the CLI**

```python
# src/arch_standard/cli.py — replace the call site at the end of _run_check
    try:
        notice = _drift_notice(root)
    except StampError as exc:
        print(f"warning: ignoring version stamp -- {exc}", file=sys.stderr)
        notice = None
    if notice is not None:
        print(notice)
```

- [ ] **Step 5: Fix the `find_spec` crash**

`importlib.util.find_spec("commons.types")` raises `ModuleNotFoundError` when `commons` itself is absent, rather than returning `None`. Both probes must tolerate it:

```python
# src/arch_standard/checks/import_contracts.py
def _importable(name: str) -> bool:
    try:
        return importlib.util.find_spec(name) is not None
    except ModuleNotFoundError:
        return False
```

Use `_importable("commons")` at line 47 and `_importable("commons.types")` at line 178.

- [ ] **Step 6: Run the suite**

Run: `uv run pytest`
Expected: green, no tracebacks.

- [ ] **Step 7: Commit**

```bash
git add src/arch_standard/version_stamp.py src/arch_standard/cli.py src/arch_standard/checks/import_contracts.py tests/
git commit -m "fix: a broken version stamp warns instead of crashing the run"
```

**Acceptance criteria:** every row of the behaviour table holds; a broken stamp yields the same exit code as a clean run; no traceback reaches the user; `arch-standard check` works in an environment with no `commons` installed.

**Dependencies:** none; parallelisable with Tasks 6–10.

---

### Task 12: Template dependency source — no placeholder default

**Files:**
- Modify: `templates/copier.yml:41-49`
- Modify: `templates/pyproject.toml.jinja:6-9`
- Test: `tests/templates/test_template_root_files.py` (extend)

**Interfaces:**
- Produces: a `dependency_source` prompt with values `git` | `index`. When `git`, `standard_git_url` is required and has **no default**. When `index`, dependencies render as plain PEP 440 specifiers resolvable from any index or `--find-links` — which is what makes Task 13's E2E test possible without publishing.

- [ ] **Step 1: Write the failing test**

```python
# tests/templates/test_template_root_files.py — append
def test_given_index_source__when_rendered__then_deps_have_no_git_url(tmp_path: Path) -> None:
    dest = tmp_path / "proj"
    copier.run_copy(
        str(TEMPLATE_ROOT),
        str(dest),
        data={"dependency_source": "index"},
        defaults=True,
        overwrite=True,
        unsafe=True,
        skip_tasks=True,
    )
    text = (dest / "pyproject.toml").read_text(encoding="utf-8")
    assert "arch-standard==" in text
    assert "git+" not in text


def test_given_git_source__when_rendered__then_deps_use_the_supplied_url(tmp_path: Path) -> None:
    dest = tmp_path / "proj"
    copier.run_copy(
        str(TEMPLATE_ROOT),
        str(dest),
        data={
            "dependency_source": "git",
            "standard_git_url": "https://example.invalid/standard.git",
        },
        defaults=True,
        overwrite=True,
        unsafe=True,
        skip_tasks=True,
    )
    text = (dest / "pyproject.toml").read_text(encoding="utf-8")
    assert "git+https://example.invalid/standard.git" in text


def test_given_the_template__when_reading_config__then_no_change_me_placeholder() -> None:
    text = (TEMPLATE_ROOT / "copier.yml").read_text(encoding="utf-8")
    assert "CHANGE_ME" not in text
```

- [ ] **Step 2: Run to verify failure**

Run: `uv run pytest tests/templates/test_template_root_files.py -v -k "index_source or git_source or change_me"`
Expected: FAIL.

- [ ] **Step 3: Rework the prompts**

```yaml
# templates/copier.yml — replace the standard_git_url block
dependency_source:
  type: str
  help: >-
    Where the generated project resolves arch-standard and arch-commons from.
    'index' emits plain version pins (use a package index, or `uv sync` with
    --find-links against locally built wheels). 'git' emits direct git
    references and requires standard_git_url below.
  choices:
    - index
    - git
  default: index

standard_git_url:
  type: str
  when: "{{ dependency_source == 'git' }}"
  help: "Git URL of your architecture-standard remote (no default -- supply your own)"
```

- [ ] **Step 4: Render both shapes**

```jinja
{# templates/pyproject.toml.jinja #}
dependencies = [
{%- if dependency_source == 'git' %}
    "arch-standard @ git+{{ standard_git_url }}@v{{ arch_standard_version }}",
    "arch-commons @ git+{{ standard_git_url }}@v{{ arch_commons_version }}#subdirectory=packages/arch-commons",
{%- else %}
    "arch-standard=={{ arch_standard_version }}",
    "arch-commons=={{ arch_commons_version }}",
{%- endif %}
]
```

Keep `[tool.hatch.metadata] allow-direct-references = true` — harmless for the index shape, required for the git shape.

- [ ] **Step 5: Run the suite**

Run: `uv run pytest tests/templates/ -v`
Expected: green. Existing template tests that relied on the old default need `data={"dependency_source": "index"}` added.

- [ ] **Step 6: Commit**

```bash
git add templates/ tests/templates/
git commit -m "feat: template dependency source is an explicit choice with no placeholder URL"
```

**Acceptance criteria:** no `CHANGE_ME` anywhere in `templates/`; both shapes render correctly; `standard_git_url` is only prompted for, and only required by, the `git` shape.

**Dependencies:** none; parallelisable with Tasks 6–11.

---

### Task 13: Subprocess end-to-end distribution gate

**Files:**
- Create: `tests/templates/test_distribution_e2e.py`
- Modify: `Makefile` (add an `e2e` target)

**Interfaces:**
- Consumes: `packaged_rules_dir` (Task 2), the `index` dependency shape (Task 12).
- Produces: the acceptance gate of section G.

This test crosses the real distribution boundary: built artifacts, a clean venv, and **no `sys.path` manipulation of the monorepo**. It is slow (~1–3 min), so mark it `@pytest.mark.e2e` and keep it out of the default run.

- [ ] **Step 1: Register the marker**

```toml
# pyproject.toml
[tool.pytest.ini_options]
testpaths = ["tests"]
addopts = "-q -m 'not e2e'"
norecursedirs = ["fixtures"]
markers = ["e2e: full build/install/generate/validate loop (slow)"]
```

- [ ] **Step 2: Write the test**

```python
# tests/templates/test_distribution_e2e.py
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import copier
import pytest

REPO = Path(__file__).resolve().parents[2]
TEMPLATE_ROOT = REPO / "templates"


def _run(cmd: list[str], cwd: Path, env: dict[str, str] | None = None) -> str:
    done = subprocess.run(cmd, cwd=cwd, env=env, capture_output=True, text=True, check=False)
    if done.returncode != 0:
        raise AssertionError(
            f"command failed ({done.returncode}): {' '.join(cmd)}\n"
            f"--- stdout ---\n{done.stdout}\n--- stderr ---\n{done.stderr}"
        )
    return done.stdout


@pytest.mark.e2e
def test_given_built_wheels__when_a_generated_project_is_installed_clean__then_all_gates_pass(
    tmp_path: Path,
) -> None:
    """The v1 distribution acceptance gate.

    Deliberately does NOT put packages/arch-commons on sys.path: the whole
    point is to prove the built artifacts are self-sufficient.
    """
    import os

    dist = tmp_path / "dist"
    _run(["uv", "build", "--out-dir", str(dist)], cwd=REPO)
    _run(["uv", "build", "--package", "arch-commons", "--out-dir", str(dist)], cwd=REPO)
    wheels = sorted(p.name for p in dist.glob("*.whl"))
    assert any(w.startswith("arch_standard-") for w in wheels), wheels
    assert any(w.startswith("arch_commons-") for w in wheels), wheels

    project = tmp_path / "acme"
    copier.run_copy(
        str(TEMPLATE_ROOT),
        str(project),
        data={"dependency_source": "index", "project_name": "Acme"},
        defaults=True,
        overwrite=True,
        unsafe=True,
        skip_tasks=True,
    )

    env = {
        **os.environ,
        "UV_FIND_LINKS": str(dist),
        # Resolve strictly from the locally built wheels.
        "UV_NO_INDEX": "1",
    }
    _run(["uv", "sync"], cwd=project, env=env)

    # The generated project's own gates.
    _run(["uv", "run", "ruff", "check", "."], cwd=project, env=env)
    _run(["uv", "run", "ruff", "format", "--check", "."], cwd=project, env=env)
    _run(["uv", "run", "mypy"], cwd=project, env=env)
    _run(["uv", "run", "pytest"], cwd=project, env=env)

    # The standard, running from the installed wheel, against the generated project.
    _run(["uv", "run", "arch-standard", "render-importlinter", "."], cwd=project, env=env)
    core = _run(["uv", "run", "arch-standard", "check", "--core", "."], cwd=project, env=env)
    assert "0 failed" in core
    assert "0 errored" in core

    full = _run(["uv", "run", "arch-standard", "check", "."], cwd=project, env=env)
    assert "0 failed" in full
    assert "0 errored" in full

    # The installed wheel carries its own catalog.
    count = _run(
        [
            "uv",
            "run",
            "python",
            "-c",
            "from arch_standard.rules.catalog import Catalog, packaged_rules_dir;"
            "print(len(Catalog.load(packaged_rules_dir())))",
        ],
        cwd=project,
        env=env,
    )
    assert count.strip().endswith("53")

    _run(["uv", "build"], cwd=project, env=env)
```

- [ ] **Step 3: Run it**

Run: `uv run pytest tests/templates/test_distribution_e2e.py -m e2e -v`
Expected: FAIL on the first real defect it finds. Work through them one at a time. **Do not** relax an assertion to get green — each failure here is a genuine distribution bug of exactly the kind this plan exists to remove. If the generated project fails full `check` because of the parked ARCH-019 warning (non-goal H7), assert on `0 failed`/`0 errored` only, as written — warnings are permitted.

- [ ] **Step 4: Retire the sys.path shortcut**

Delete the `monkeypatch.syspath_prepend` line in `tests/templates/test_generated_project_end_to_end.py:38-39` and let that test keep its in-process scope, or delete the test if this one fully subsumes it. State which you chose in the commit message.

- [ ] **Step 5: Add the Makefile target**

```make
e2e:
	uv run pytest tests/templates/test_distribution_e2e.py -m e2e -v
```

- [ ] **Step 6: Commit**

```bash
git add tests/templates/ pyproject.toml Makefile
git commit -m "test: prove the built wheels install and validate outside the source checkout"
```

**Acceptance criteria:** the e2e test passes from a clean checkout with no network index; no test monkeypatches `sys.path` to reach `packages/arch-commons`.

**Dependencies:** Tasks 2, 5, 10, 12 (needs packaging, honest outcomes, no ERROR rows, and the `index` shape).

---

### Task 14: CI integrity — dogfooding and release governance

**Files:**
- Modify: `.github/workflows/ci.yml`
- Modify: `Makefile`

**Interfaces:**
- Consumes: everything above.

**The dogfooding question, answered honestly.** The brief asks for `arch-standard check .` in this repo's CI. After Task 5, that command **will fail on this repo**, and correctly so: `arch_standard/` is a validator package, not a bounded-context tree, so it resolves to zero contexts — which Task 5 defines as ERROR precisely so a misconfigured project cannot go green. The repo cannot satisfy the DDD structural rules because it is not a DDD application, and the brief says not to weaken rules to make it pass. So the resolution is: **dogfood against conforming targets** (the fixtures and a freshly generated project, which is what "the standard validates real projects" actually means), and run `release-check` against this repo, where catalog governance genuinely applies. This is the "explicitly identify what must be fixed for self-validation" answer the brief asked for.

- [ ] **Step 1: Add the CI steps**

```yaml
      # Dogfooding: the validator must pass on conforming projects and fail on violations.
      - run: uv run arch-standard check tests/fixtures/good_project
      - run: uv run arch-standard check tests/fixtures/modular_project
      - name: the violation fixture must actually fail
        run: |
          if uv run arch-standard check tests/fixtures/bad_project; then
            echo "bad_project passed -- the validator is not detecting violations"
            exit 1
          fi
      # Catalog governance: the compatibility policy is enforced, not advisory.
      - run: uv run arch-standard release-check --version 0.1.0
```

- [ ] **Step 2: Add the matching Makefile targets**

```make
selfcheck:
	uv run arch-standard check tests/fixtures/good_project
	uv run arch-standard check tests/fixtures/modular_project
	uv run arch-standard release-check --version 0.1.0
```

- [ ] **Step 3: Verify locally**

Run: `make selfcheck` (or the three commands directly)
Expected: all pass. Confirm `release-check`'s exact flag name first with `uv run arch-standard release-check --help` — if it differs from `--version`, use the real one.

- [ ] **Step 4: Correct the CHANGELOG's false claim**

`CHANGELOG.md:4-5` currently asserts that `release-check` enforces the policy. Until this task it did not. Now that CI runs it, the sentence becomes true — verify the wording matches reality and adjust it if not.

- [ ] **Step 5: Commit**

```bash
git add .github/workflows/ci.yml Makefile CHANGELOG.md
git commit -m "ci: dogfood the validator on real fixtures and enforce the compatibility policy"
```

**Acceptance criteria:** CI runs the validator on passing and failing fixtures and asserts both directions; `release-check` runs on every push; the CHANGELOG's enforcement claim is true.

**Dependencies:** Tasks 5, 10 (check semantics must be final before wiring CI to them).

---

### Task 15: Release readiness review

**Files:**
- Modify: `CHANGELOG.md`
- Modify: `docs/superpowers/specs/2026-09-05-architecture-standard-v1-design.md` (§17 rows H, J, R only)

**Interfaces:** none — this is the closing task.

- [ ] **Step 1: Close the three trade-off rows**

Rows H (packaged rules unreachable when installed), J (no self-validation in CI) and R (core rules without checks) are the audit findings this plan closes. Mark each resolved in §17 with the resolving commit, matching how row P was closed previously.

- [ ] **Step 2: Record the catalog changes in the CHANGELOG**

Three rules changed `automation`/`validation.tool` (ARCH-024, 042, 045) and three more changed `automation` (ARCH-007, 008, 025). Per spec §16.3 these are **patch**-level changes ("wording, rationale, examples, automation tier"). No rule changed `level`, so no migration notes are required. Verify that claim:

Run: `uv run arch-standard release-check --version 0.1.1`
Expected: passes, classifying the change as patch.

- [ ] **Step 3: Run the whole gate**

```bash
uv run ruff check . && uv run ruff format --check . && uv run mypy && uv run pytest
uv run --package arch-commons pytest -c packages/arch-commons/pyproject.toml packages/arch-commons/tests
uv run arch-standard docs --check
make selfcheck
make e2e
```

Expected: every command green.

- [ ] **Step 4: Commit**

```bash
git add CHANGELOG.md docs/superpowers/specs/
git commit -m "docs: close trade-off rows H/J/R and record the v1 hardening catalog changes"
```

**Acceptance criteria:** section G's gate passes end to end.

**Dependencies:** all previous tasks.

---

## C. Dependency graph

```text
Task 1  (strict Catalog.load)
  └── Task 2  (package catalog + importlib.resources)
        └──────────────────────────────┐
Task 3  (ERROR / NOT_AUTOMATED)        │
  ├── Task 4  (full-run completeness)  │
  │     └── Task 5  (empty-scan safety)│
  │           └──────────────┐         │
Task 6  (attribute 007/008/013/025)    │   ← same file as Task 7: strictly sequential
  └── Task 7  (5 new contracts)        │
Task 8  (ARCH-037 structure)  ─────────┤
Task 9  (ARCH-033 AST, core)  ─────────┤
        └── Task 10 (relabel 3 + META-TEST)   ← convergence: needs 6,7,8,9
                  └── Task 14 (CI)     │
Task 11 (stamp safety)  ───────────────┤
Task 12 (template dep source) ─────────┤
                  └── Task 13 (E2E)  ──┴── needs 2, 5, 10, 12
                            └── Task 15 (release readiness)  ← needs all
```

**Strictly sequential:** 1→2; 3→4→5; 6→7 (same file); {6,7,8,9}→10; {2,5,10,12}→13; {5,10}→14; all→15.

**Safely parallel:** three independent lanes can run concurrently after Task 3 lands —
- **Lane A (catalog/distribution):** 1 → 2 → 12
- **Lane B (validator honesty):** 3 → 4 → 5, then 6 → 7, with 8 and 9 alongside
- **Lane C (safety):** 11 (touches only `version_stamp.py`/`cli.py`/`import_contracts.py`'s two probe functions)

Lane C's edit to `import_contracts.py` is confined to `_commons_root_available`/`_commons_types_importable` and does not collide with Tasks 6–7's edits to `build_contracts`/`rule_ids`, but if running them truly concurrently, land Lane C first to keep the merge trivial.

Given the subagent-driven workflow is one focused task at a time, the recommended order is simply: **1, 2, 3, 4, 5, 11, 6, 7, 8, 9, 10, 12, 13, 14, 15.** Task 11 is pulled early because it is self-contained and removes a crash that will otherwise confuse every later manual verification.

---

## D. Risks

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Moving `rules/` to `src/arch_standard/rules/_catalog/` breaks an unnoticed reference (Makefile, CI, docgen, snapshot tooling, a test's hardcoded path) | High | Medium | Task 2 Step 5's grep is mandatory, not advisory. `docs --check` and the snapshot round-trip are the canaries. |
| Task 4 makes `arch-standard check` exit 1 across the whole repo until Task 10 lands | Certain | Medium | This is the intended intermediate state and is called out in Task 4 Step 5. Do not "fix" it by softening the ERROR rule; land Task 10. |
| Attribution (Task 6) makes one broken contract report 5 rule IDs at once, which could read as noise | Medium | Low | Accepted trade-off, recorded in D2. The alternative — separate contracts duplicating the same assertion — is worse. |
| ARCH-033's AST heuristic produces false positives on legitimate non-UoW commits | Medium | Medium | The heuristic is deliberately narrow (commit on a receiver not bound by an enclosing `with`). If a real project trips it wrongly, the ADR waiver process (spec §13) is the sanctioned escape hatch — do not widen the rule silently. |
| ARCH-011's overlapping source/forbidden module lists behave differently than assumed in a future import-linter version | Low | Medium | Task 7 Step 5's negative test asserts the contract actually FAILs on a real violation, which would catch a behaviour change. |
| The E2E test is slow and flaky in CI (network, uv cache, Windows path handling) | Medium | Medium | `UV_NO_INDEX=1` removes network dependence. Marked `e2e` and excluded from the default run. Run it as a separate CI job, not inline. |
| `uv build --package arch-commons` produces a wheel whose name differs from the assumed `arch_commons-*` prefix | Low | Low | Task 13 asserts on the prefix and fails loudly with the actual list. |
| Relabelling ARCH-024/042/045 to `review` reads as a downgrade of the standard | Low | Low | It is an honesty correction, not a weakening: the rules' `level` is untouched, and they were never enforced. Record this framing in the CHANGELOG (Task 15). |

---

## E. Explicit design decisions

> **STATUS: RATIFIED 2026-09-09.** The positions below were reviewed and approved before execution. D1, D2, D5 and D6 stand as written. D3 is confirmed **out of scope** — see the ratified constraints. D4 stands as written. Executors must treat these as settled: do not re-litigate them mid-task, and do not silently adopt an alternative. If a task cannot be completed without contradicting one, **stop and report** rather than deviating.

### Ratified execution constraints

These were recorded at execution kickoff and bind every task in this plan:

1. **Packaging (D1) — APPROVED.** Move `rules/` into the `arch_standard` package and resolve it with `importlib.resources`. A `force-include`-only solution that produces different source-checkout vs. installed-package behaviour is **explicitly rejected**.
2. **E2E distribution test (D2/Task 13) — APPROVED.** Build both `arch-standard` and `arch-commons` as real wheels and exercise them in a clean environment via `UV_FIND_LINKS` + `UV_NO_INDEX`. The test **must not** reach the monorepo through `sys.path` manipulation.
3. **External publication (D3) — DO NOT DECIDE.** Do not invent or choose: GitHub organisation/repository ownership; PyPI vs. a private index; publishing credentials; release-automation credentials; or who performs the final `v0.1.0` publication. External publication is a **manual human configuration point**. Tasks may prepare for it; no task may assume, fabricate, or hardcode any of it.
4. **ARCH-033 (Task 9) — NARROW BY MANDATE.** The AST check must be explicit about the *syntactic* property it actually proves, and must not pretend to prove arbitrary semantic use-case behaviour. It proves exactly one thing: a `.commit()` call whose receiver is not bound by an enclosing `with`. Its docstring, its findings' messages, and the rule's `validation.detail` must all say so plainly. Widening it into inferred "does this method change state" reasoning is out of bounds.
5. **Scope control.** This plan is strictly the nine acceptance-audit blockers. Do not expand into H5–H10, M1–M9, the Software Factory, Skills, the Architecture Reviewer, or multi-agent orchestration unless a direct dependency makes it genuinely unavoidable — and if it does, stop and report before proceeding.
6. **Do not redesign what the audit found solid.** Off-limits for redesign: `arch-commons` dependency direction; the compatibility mechanism; the `commons.types` / `shared_kernel` / `<context>/shared/` terminology split; the existing `--core` SKIP behaviour; the rendered import-linter contracts; the layered template structure; `Uuid7IdGenerator`; `SystemClock`; frozen events; the `0.1.0` baseline.
7. **Escalation trigger.** Stop and report if an implementation decision would materially change the Architecture Standard's *contract* (rule levels, rule semantics, the stamp shape, the catalog's public meaning) rather than merely fixing one of the nine blockers.

---

The following are the original positions, retained for the reasoning behind each.

**D1 — Catalog location (Task 2).** *Position: move the YAML into `src/arch_standard/rules/_catalog/`; the repo-root `rules/` directory disappears.*
The alternative is keeping `rules/` at the root for authoring ergonomics and using a hatchling `force-include`. Rejected because `force-include` populates only the built wheel, so a source checkout and an installed wheel would resolve through different code paths — reintroducing the exact bug class this plan removes. **Cost of the position:** the most human-visible convention in the repo changes; every doc or muscle-memory reference to `rules/*.yaml` moves. **Overrule if** you consider root-level `rules/` part of the standard's public identity — in which case Task 2 keeps the root directory and adds an explicit dev-checkout branch, and we accept two resolution paths.

**D2 — Attribution vs. distinct contracts (Task 6).** *Position: name ARCH-007/008/013/025 on the contracts that already enforce them.*
This is honest (the assertion genuinely runs) and free. The cost is granularity: a single broken layers contract reports five rule IDs, so a reader cannot tell which facet was violated. **Overrule if** you want per-rule diagnostic precision, which means emitting separate near-duplicate contracts and accepting slower runs and more `.importlinter` noise.

**D3 — What "publishing" means for v0.1.0 (Task 12, and out of scope for execution).** *Position: this plan makes the artifacts releasable but performs no release.*
The E2E test deliberately does not depend on publication (Q1). Someone must still decide, **manually**: (a) whether there will be a git remote at all and its URL; (b) whether `arch-standard`/`arch-commons` go to PyPI, a private index, or stay git-referenced; (c) who tags `v0.1.0`. This plan invents none of that. **Needed before** a real consumer can generate a project with `dependency_source: git`.

**D4 — What dogfooding means for a repo that is not a DDD application (Task 14).** *Position: run the validator against conforming fixtures and a generated project, plus `release-check` on this repo; do not run `arch-standard check .` on the repo root.*
The brief asked for `check .` literally, but after Task 5 that resolves to zero contexts and correctly ERRORs. **Overrule if** you would rather this repo carry a token bounded context purely to satisfy self-validation — not recommended, as it is architecture theatre.

**D5 — ARCH-042's fate (Task 10).** *Position: relabel to `review`.*
The cheap half (does `application/ports.py` exist at all?) is checkable today; the rule's actual threshold ("3+ ports shared across use-case modules") needs cross-module usage analysis. **Overrule if** you want the cheap half implemented now as a partial check — that adds a task between 8 and 10 and moves ARCH-042 from column B to column A.

**D6 — Whether `NOT_AUTOMATED` rules should be printed by default (Tasks 3–4).** *Position: print them, in the main list, counted separately.*
It makes the run longer (53 rows) but is the whole point of the honesty work: a reader sees exactly how much of the standard is human-reviewed. **Overrule if** you prefer them collapsed behind a `--show-manual` flag, which keeps everyday output shorter at the cost of making the manual surface easy to forget.

---

## F. Definition of Done

Plan 3.1 is done when **all** of the following hold on `master`:

1. `uv run pytest` green; `uv run pytest -m e2e` green.
2. `uv run ruff check .`, `uv run ruff format --check .`, `uv run mypy` green for both packages.
3. `uv run arch-standard docs --check` reports the committed document current.
4. `tests/rules/test_machine_backed_honesty.py` passes — no rule claims a machine validator without a check, and core is 12/12.
5. A built wheel contains the catalog; a clean-venv install loads 53 rules.
6. All four false-green scenarios (empty dir, wrong layout, unrelated files, zero contexts) exit non-zero.
7. A malformed `.arch-standard` produces the same exit code as a clean run, with no traceback.
8. No `CHANGE_ME` string anywhere in `templates/`.
9. No test reaches `packages/arch-commons` via `sys.path` manipulation.
10. CI runs the validator on passing **and** failing fixtures, and runs `release-check`.
11. Spec §17 rows H, J and R are marked resolved.
12. Every non-goal listed in the header is still untouched.

---

## G. Final v1 acceptance criteria

One command chain, run from a clean checkout, must pass end to end. This is the gate that justifies declaring `ARCHITECTURE STANDARD v1 STATUS: READY`:

```bash
# 1. source checkout is healthy
uv run ruff check . && uv run ruff format --check . && uv run mypy && uv run pytest
uv run --package arch-commons pytest -c packages/arch-commons/pyproject.toml packages/arch-commons/tests
uv run arch-standard docs --check

# 2. the standard validates real projects, and detects real violations
make selfcheck

# 3. build distribution -> clean env -> generate -> install -> validate
make e2e
```

Step 3 internally proves, in order: both wheels build; a clean venv installs them with no index and no monorepo path; `copier` generates a project; `uv sync` resolves the declared dependencies from the built artifacts; the generated project passes `ruff`, `ruff format --check`, `mypy --strict` and `pytest`; `arch-standard render-importlinter` writes real contracts; `arch-standard check --core .` reports `0 failed, 0 errored`; `arch-standard check .` reports `0 failed, 0 errored` across all 53 rules; the installed wheel loads its own 53-rule catalog; and the generated project itself builds a wheel.

**What this gate does not claim:** that `v0.1.0` is published (D3 is a human decision), that every rule is machine-enforced (7 MUST-family rules remain honestly `review`), or that the non-goals H5–H10 and M1–M9 are fixed. It claims exactly this: the standard is honest about what it enforces, it installs and runs outside its own repository, and it cannot report success when it has verified nothing.
