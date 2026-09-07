# Distribution and Release Engineering — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the Architecture Standard usable as the base of many independent repositories, per spec Section 16.3 and Section 8.1 — `arch-commons` as a real, separately-versioned, non-vendored package; a version stamp + drift notice; a rule-catalog compatibility policy that is actually enforced, not just documented; CHANGELOG tooling; and a `copier` project template that generates a project which passes the standard's own core checks out of the box.

**Architecture:** `arch-commons` becomes a second package in this repo, added as a `uv` workspace member (`packages/arch-commons/`), importable as `commons.types` / `commons.infrastructure` (distribution name `arch-commons`, import name `commons` — the rule catalog already writes its examples this way). It is never vendored under any project's `src/`. The validator's ARCH-034/035 checks, which currently assume `commons/` is vendored under the project being checked, are corrected to also recognize an installed `arch-commons`. Release engineering (version stamp, compatibility policy, CHANGELOG) is new tooling under `src/arch_standard/release/` and a handful of new `arch-standard` subcommands, built around a committed catalog snapshot (`rules/.released/<version>/`) that gives the compatibility checker and the changelog generator something concrete to diff against — there is no tag-based release process yet, so a snapshot directory is the simplest mechanism that actually works today. The `copier` template lives in `templates/` and generates the spec's own running example (`sales/orders`) as a real, wired, checkable vertical slice, proving end-to-end that a freshly generated project passes `arch-standard check --core`.

**Tech Stack:** Python 3.12+, `uv` workspaces, `pytest`, `pydantic` v2, `PyYAML`, `tomllib` (stdlib), `import-linter` + `grimp`, `ruff`, `mypy --strict`, `sqlalchemy>=2.0` (arch-commons infrastructure only), `copier>=9`.

**Spec:** `docs/superpowers/specs/2026-09-05-architecture-standard-v1-design.md` — read Section 0 (locked framing decisions, esp. Distribution/`commons/`/Read side rows), Section 2 (canonical tree, esp. the `.arch-standard` line and the "not vendored" note), Section 6.2/7.2/7.3 (the `sales/orders` worked example this plan's template reuses, the `UnitOfWork` Protocol verbatim, the outbox), Section 8.1 (`arch-commons`), Section 16.3 (versioning and distribution — the compatibility table, the version stamp shape, the CHANGELOG requirement), Section 17 rows C/K (multi-repo topology deferred to v2; import-contract coarse-signal history relevant to Task 10), Section 18.1 (standard-owned base classes vs pure conventions — grounds the duck-typed event-draining convention this plan uses).

**Not in this plan:** publishing `arch-standard`/`arch-commons` to a real package index (generated projects depend on this repo via a git URL until that happens — a stated limitation, not solved here); the Superpowers skill and the `architecture-reviewer` subagent (spec Section 16, items 3–4 of the reuse pipeline); ADR waiver CI wiring (trade-off log row J, still open).

## Global Constraints

- Python 3.12+. `from __future__ import annotations` at the top of every module (including every file under `packages/arch-commons/src/`).
- Root repo passes `uv run ruff check .`, `uv run ruff format --check .`, `uv run mypy` (strict), `uv run pytest`, `uv run arch-standard docs --check`. `packages/arch-commons` is a separate workspace member with its own `[tool.mypy]`/`[tool.pytest.ini_options]`, checked via `uv run --package arch-commons mypy` and `uv run --package arch-commons pytest` — mypy's explicit `files` list and pytest's explicit `testpaths` do not descend into `packages/`, so these do not run automatically from the root invocation. Ruff *does* discover `packages/arch-commons` files when run as `uv run ruff check .` from the root (nearest-`pyproject.toml` hierarchical config resolution), so its own `[tool.ruff]` block must mirror the root's settings.
- Rule catalog compatibility policy (spec Section 16.3): add a `MUST`, or raise a rule's level to `MUST` → **major**. Add a `SHOULD`/`MAY`, or tighten a `SHOULD` → **minor**. Wording/rationale/examples/automation only → **patch**. A new `MUST` never lands directly — it enters as `SHOULD` in a minor and is promoted to `MUST` in the next major.
- This repo has no separate "catalog version" field: `[project].version` in the root `pyproject.toml` **is** the rule catalog's version. This is a scope decision this plan makes (the spec names the standard's version as one of three semver'd artifacts but does not say where it lives) — reusing the package version avoids inventing a second version number that could drift from the first.
- `commons/` is **never** vendored under any project's `src/`. Every reference to it in this plan is `import commons.types...` / `import commons.infrastructure...` from the installed `arch-commons` package (ARCH-015/016/034/035, spec Section 8.1).
- Never change a rule's `level` in `rules/*.yaml` to make a test pass. Change the test.
- Tests land in the same commit as the code. Conventional Commits. Every commit message ends with:
  ```
  Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
  Claude-Session: https://claude.ai/code/session_01GEq9yHV4hbB35DxtL11UFL
  ```
- Run `uv run ruff format .` (and, for `packages/arch-commons` changes, `uv run --package arch-commons ruff format .`) before committing.
- `tests/fixtures/` stays excluded from this repo's own ruff/mypy/pytest collection. `templates/*.jinja` files are not valid standalone Python and are never picked up by ruff/mypy (ruff/mypy only look at `*.py`); the one real (non-templated) Python file this plan adds under `templates/` — there is none, `render-importlinter` is a normal `arch-standard` subcommand, not a template-local script — so no new exclude entries are needed.
- Jinja-authoring rule for every `*.py.jinja` file in this plan: never mix a literal Python `{`/`}` (an f-string placeholder) directly adjacent to a `{{ jinja_expr }}` — Jinja's tokenizer does not require whitespace before `{{`, so `{{{ x }}...}` misparses. Use string concatenation (`"literal " + str(value)`) instead of f-strings wherever a template variable and a literal brace would otherwise collide.

---

## File Structure

```text
pyproject.toml                                        # MODIFY: uv workspace + arch-commons dev dep
packages/arch-commons/
├── pyproject.toml                                     # CREATE
├── src/commons/
│   ├── __init__.py                                    # CREATE
│   ├── types/
│   │   ├── __init__.py                                # CREATE
│   │   ├── errors.py                                  # CREATE: DomainError, ApplicationError
│   │   ├── identity.py                                # CREATE: EntityId
│   │   ├── pagination.py                              # CREATE: Page
│   │   ├── events.py                                  # CREATE: DomainEvent Protocol
│   │   ├── clock.py                                   # CREATE: Clock Protocol
│   │   ├── event_bus.py                                # CREATE: EventBus Protocol
│   │   ├── id_generator.py                              # CREATE: IdGenerator Protocol
│   │   └── unit_of_work.py                               # CREATE: UnitOfWork Protocol
│   └── infrastructure/
│       ├── __init__.py                                # CREATE
│       ├── in_memory_unit_of_work.py                  # CREATE
│       ├── in_memory_event_bus.py                     # CREATE
│       ├── system_clock.py                            # CREATE
│       ├── uuid7_id_generator.py                      # CREATE
│       ├── sqlalchemy_unit_of_work.py                 # CREATE
│       └── outbox.py                                  # CREATE
└── tests/
    ├── test_package_importable.py                     # CREATE
    ├── types/ (test_errors.py, test_identity_pagination.py, test_events_clock.py,
    │           test_event_bus_id_generator.py, test_unit_of_work.py)  # CREATE
    └── infrastructure/ (test_leaf_adapters.py, test_sqlalchemy_unit_of_work.py,
                          test_outbox.py)                                # CREATE
src/arch_standard/
├── checks/import_contracts.py                          # MODIFY: importability-based commons gating
├── version_stamp.py                                    # CREATE
├── cli.py                                              # MODIFY: drift notice + 4 new subcommands
└── release/
    ├── __init__.py                                     # CREATE
    ├── snapshot.py                                     # CREATE
    ├── diff.py                                         # CREATE
    ├── compatibility.py                                # CREATE
    └── changelog.py                                    # CREATE
rules/.released/0.1.0/*.yaml                            # CREATE: baseline catalog snapshot
CHANGELOG.md                                            # CREATE
tests/
├── test_version_stamp.py                               # CREATE
├── test_cli_drift_notice.py                             # CREATE
├── checks/test_import_contracts.py                      # MODIFY: installed-commons regression
├── release/ (test_snapshot.py, test_diff.py, test_compatibility.py,
│             test_release_check_cli.py, test_changelog.py,
│             test_changelog_cli.py)                                   # CREATE
└── test_real_catalog.py                                  # MODIFY: CHANGELOG.md exists + header
templates/
├── copier.yml                                          # CREATE
├── main.py.jinja                                        # CREATE
├── pyproject.toml.jinja                                  # CREATE
├── contexts.toml.jinja                                    # CREATE
├── .arch-standard.jinja                                    # CREATE
├── Makefile.jinja                                           # CREATE
├── .github/workflows/ci.yml.jinja                             # CREATE
├── bootstrap/__init__.py.jinja                                # CREATE
└── src/{{ context_name }}/
    ├── entrypoints/providers.py.jinja                          # CREATE
    └── {{ aggregate_module }}/
        ├── domain/model/
        │   ├── {{ aggregate_name }}.py.jinja                     # CREATE
        │   ├── exceptions.py.jinja                                # CREATE
        │   ├── events.py.jinja                                     # CREATE
        │   └── ports.py.jinja                                       # CREATE
        ├── application/{{ aggregate_name }}_service.py.jinja         # CREATE
        └── infrastructure/{{ aggregate_name }}_repository.py.jinja     # CREATE
tests/templates/
├── conftest.py                                          # CREATE
├── test_template_root_files.py                          # CREATE
├── test_template_bootstrap_providers.py                  # CREATE
├── test_template_domain_layer.py                          # CREATE
├── test_template_application_infrastructure.py             # CREATE
├── test_render_importlinter.py                               # CREATE
└── test_generated_project_end_to_end.py                        # CREATE
```

---

## Group A: `arch-commons` — a real, separately-versioned package

**Worked example first.** Section 6.2/7.2 of the spec walk through `sales/orders`: `OrderService` needs a `UnitOfWork` it can `with`, an `EventBus` to `publish_all` on, and a repository whose `add`/`get` it calls — none of those three things exist as *code* anywhere in this repo yet, only as Protocol signatures in the spec's prose. This group makes them real, importable, and owned by nobody's `src/`.

### Task 1: Workspace scaffolding — `arch-commons` exists and is importable

**Files:**
- Create: `packages/arch-commons/pyproject.toml`
- Create: `packages/arch-commons/src/commons/__init__.py`
- Create: `packages/arch-commons/tests/test_package_importable.py`
- Modify: `pyproject.toml` (root)

**Interfaces:**
- Produces: the `commons` import name, the `arch-commons` distribution name, a `uv` workspace with `packages/*` as members, `arch-commons` available as a dev dependency of the root `arch-standard` package (used by Task 10's regression test).

- [ ] **Step 1: Write the failing test**

```python
# packages/arch-commons/tests/test_package_importable.py
from __future__ import annotations


def test_given_arch_commons_installed__when_imported__then_succeeds() -> None:
    import commons

    assert commons is not None
```

- [ ] **Step 2: Run it to confirm the package doesn't exist yet**

Run: `uv run --package arch-commons pytest packages/arch-commons/tests/test_package_importable.py -v`
Expected: FAIL — uv reports no such package (`packages/arch-commons` isn't a workspace member yet, and its `pyproject.toml` doesn't exist).

- [ ] **Step 3: Create the package and wire the workspace**

```toml
# packages/arch-commons/pyproject.toml
[project]
name = "arch-commons"
version = "0.1.0"
description = "Architecture Standard — shared technical package (commons.types, commons.infrastructure)"
requires-python = ">=3.12"
dependencies = []

[project.optional-dependencies]
sqlalchemy = ["sqlalchemy>=2.0"]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["src/commons"]

[dependency-groups]
dev = ["pytest>=8", "ruff>=0.6", "mypy>=1.11", "sqlalchemy>=2.0"]

[tool.ruff]
line-length = 100
src = ["src", "tests"]

[tool.ruff.lint]
select = ["E", "F", "I", "UP", "B", "SIM", "TID"]

[tool.mypy]
strict = true
files = ["src", "tests"]

[tool.pytest.ini_options]
testpaths = ["tests"]
addopts = "-q"
```

```python
# packages/arch-commons/src/commons/__init__.py
from __future__ import annotations
```

```toml
# pyproject.toml (root) — add these two tables, and add "arch-commons" to dev
[tool.uv.workspace]
members = ["packages/*"]

[tool.uv.sources]
arch-commons = { workspace = true }

[dependency-groups]
dev = ["pytest>=8", "ruff>=0.6", "mypy>=1.11", "types-pyyaml", "arch-commons"]
```

Also add a second line to the root `Makefile`'s `test` target so both workspace members run in one `make test`:

```makefile
test:
	uv run pytest
	uv run --package arch-commons pytest
```

And add an `arch-commons` job to `.github/workflows/ci.yml`, after the existing `validate` job's steps:

```yaml
      - run: uv run --package arch-commons ruff check packages/arch-commons
      - run: uv run --package arch-commons ruff format --check packages/arch-commons
      - run: uv run --package arch-commons mypy
      - run: uv run --package arch-commons pytest
```

- [ ] **Step 4: Sync and run the test to verify it passes**

Run: `uv sync && uv run --package arch-commons pytest packages/arch-commons/tests/test_package_importable.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add pyproject.toml Makefile .github/workflows/ci.yml packages/arch-commons/pyproject.toml \
        packages/arch-commons/src/commons/__init__.py packages/arch-commons/tests/test_package_importable.py \
        uv.lock
git commit -m "$(cat <<'EOF'
feat: scaffold arch-commons as a uv workspace member

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01GEq9yHV4hbB35DxtL11UFL
EOF
)"
```

### Task 2: `commons.types.errors` — `DomainError`, `ApplicationError`

**Files:**
- Create: `packages/arch-commons/src/commons/types/__init__.py`
- Create: `packages/arch-commons/src/commons/types/errors.py`
- Test: `packages/arch-commons/tests/types/test_errors.py`

**Interfaces:**
- Produces: `commons.types.errors.DomainError`, `commons.types.errors.ApplicationError` (both plain `Exception` subclasses). `DomainError` is the base every concrete domain exception in a generated project subclasses (ARCH-032); it is also what Task 22's template uses.

- [ ] **Step 1: Write the failing test**

```python
# packages/arch-commons/tests/types/test_errors.py
from __future__ import annotations

import pytest


def test_given_domain_error__when_raised__then_it_is_an_exception() -> None:
    from commons.types.errors import DomainError

    with pytest.raises(DomainError):
        raise DomainError("insufficient credit")


def test_given_application_error__when_raised__then_it_is_distinct_from_domain_error() -> None:
    from commons.types.errors import ApplicationError, DomainError

    assert not issubclass(ApplicationError, DomainError)
    assert not issubclass(DomainError, ApplicationError)
```

- [ ] **Step 2: Run to verify it fails**

Run: `uv run --package arch-commons pytest packages/arch-commons/tests/types/test_errors.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'commons.types'`

- [ ] **Step 3: Implement**

```python
# packages/arch-commons/src/commons/types/__init__.py
from __future__ import annotations
```

```python
# packages/arch-commons/src/commons/types/errors.py
from __future__ import annotations


class DomainError(Exception):
    """Base for expected business errors raised by domain/ and application/ (ARCH-032)."""


class ApplicationError(Exception):
    """Base for application-layer errors that are not business-rule violations."""
```

- [ ] **Step 4: Run to verify it passes**

Run: `uv run --package arch-commons pytest packages/arch-commons/tests/types/test_errors.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add packages/arch-commons/src/commons/types/__init__.py packages/arch-commons/src/commons/types/errors.py \
        packages/arch-commons/tests/types/test_errors.py
git commit -m "$(cat <<'EOF'
feat: add commons.types.errors (DomainError, ApplicationError)

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01GEq9yHV4hbB35DxtL11UFL
EOF
)"
```

### Task 3: `commons.types.identity` + `commons.types.pagination` — `EntityId`, `Page`

**Files:**
- Create: `packages/arch-commons/src/commons/types/identity.py`
- Create: `packages/arch-commons/src/commons/types/pagination.py`
- Test: `packages/arch-commons/tests/types/test_identity_pagination.py`

**Interfaces:**
- Produces: `EntityId(value: str)` — frozen dataclass, non-empty `value`, base class every project's typed IDs subclass (e.g. Task 22's `OrderId(EntityId)`). `Page[T](items: tuple[T, ...], total: int)` — frozen generic dataclass, the exact shape shown in ARCH-016's `correct` example in `rules/dependencies.yaml`, generalized over item type.

- [ ] **Step 1: Write the failing test**

```python
# packages/arch-commons/tests/types/test_identity_pagination.py
from __future__ import annotations

import pytest


def test_given_entity_id__when_constructed_with_value__then_str_returns_it() -> None:
    from commons.types.identity import EntityId

    entity_id = EntityId(value="ord-1")
    assert str(entity_id) == "ord-1"


def test_given_entity_id__when_constructed_empty__then_raises() -> None:
    from commons.types.identity import EntityId

    with pytest.raises(ValueError):
        EntityId(value="")


def test_given_entity_id__when_constructed__then_it_is_frozen() -> None:
    from commons.types.identity import EntityId

    entity_id = EntityId(value="ord-1")
    with pytest.raises(Exception):  # dataclasses.FrozenInstanceError
        entity_id.value = "ord-2"  # type: ignore[misc]


def test_given_page__when_constructed__then_holds_items_and_total() -> None:
    from commons.types.pagination import Page

    page: Page[int] = Page(items=(1, 2, 3), total=10)
    assert page.items == (1, 2, 3)
    assert page.total == 10
```

- [ ] **Step 2: Run to verify it fails**

Run: `uv run --package arch-commons pytest packages/arch-commons/tests/types/test_identity_pagination.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'commons.types.identity'`

- [ ] **Step 3: Implement**

```python
# packages/arch-commons/src/commons/types/identity.py
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class EntityId:
    """Base for every project's typed aggregate IDs, e.g. ``class OrderId(EntityId): pass``."""

    value: str

    def __post_init__(self) -> None:
        if not self.value:
            raise ValueError("EntityId value must not be empty")

    def __str__(self) -> str:
        return self.value
```

```python
# packages/arch-commons/src/commons/types/pagination.py
from __future__ import annotations

from dataclasses import dataclass
from typing import Generic, TypeVar

T = TypeVar("T")


@dataclass(frozen=True)
class Page(Generic[T]):
    items: tuple[T, ...]
    total: int
```

- [ ] **Step 4: Run to verify it passes**

Run: `uv run --package arch-commons pytest packages/arch-commons/tests/types/test_identity_pagination.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add packages/arch-commons/src/commons/types/identity.py packages/arch-commons/src/commons/types/pagination.py \
        packages/arch-commons/tests/types/test_identity_pagination.py
git commit -m "$(cat <<'EOF'
feat: add commons.types.identity (EntityId) and pagination (Page)

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01GEq9yHV4hbB35DxtL11UFL
EOF
)"
```

### Task 4: `commons.types.events` + `commons.types.clock` — `DomainEvent`, `Clock`

**Files:**
- Create: `packages/arch-commons/src/commons/types/events.py`
- Create: `packages/arch-commons/src/commons/types/clock.py`
- Test: `packages/arch-commons/tests/types/test_events_clock.py`

**Interfaces:**
- Produces: `DomainEvent` — a `runtime_checkable` structural `Protocol` requiring `occurred_at: datetime` (this is the type spec Section 7.2's `UnitOfWork.collect_new_events(self) -> Iterable[DomainEvent]` refers to; concrete events like `OrderCreated` stay in each aggregate module's own `domain/model/events.py` per Section 3.4/5.3 — this is only the minimal shape the commons machinery needs to structurally recognize one). `Clock.now() -> datetime` — the port that keeps `datetime.now()` out of `domain/`/`application/` (spec Section 5.1, ARCH-004).

- [ ] **Step 1: Write the failing test**

```python
# packages/arch-commons/tests/types/test_events_clock.py
from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime


def test_given_a_frozen_dataclass_with_occurred_at__when_checked__then_is_a_domain_event() -> None:
    from commons.types.events import DomainEvent

    @dataclass(frozen=True)
    class WidgetCreated:
        widget_id: str
        occurred_at: datetime

    event = WidgetCreated(widget_id="w-1", occurred_at=datetime.now(UTC))
    assert isinstance(event, DomainEvent)


def test_given_an_object_without_occurred_at__when_checked__then_is_not_a_domain_event() -> None:
    from commons.types.events import DomainEvent

    assert not isinstance(object(), DomainEvent)


def test_given_a_clock_implementation__when_now_called__then_returns_a_datetime() -> None:
    from commons.types.clock import Clock

    class FixedClock:
        def now(self) -> datetime:
            return datetime(2026, 1, 1, tzinfo=UTC)

    clock: Clock = FixedClock()
    assert clock.now() == datetime(2026, 1, 1, tzinfo=UTC)
```

- [ ] **Step 2: Run to verify it fails**

Run: `uv run --package arch-commons pytest packages/arch-commons/tests/types/test_events_clock.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'commons.types.events'`

- [ ] **Step 3: Implement**

```python
# packages/arch-commons/src/commons/types/events.py
from __future__ import annotations

from datetime import datetime
from typing import Protocol, runtime_checkable


@runtime_checkable
class DomainEvent(Protocol):
    """The minimal structural shape ``UnitOfWork.collect_new_events`` needs
    (spec Section 7.2). Concrete events (frozen, past-tense, ARCH-023) live in
    each aggregate module's own domain/model/events.py, never here."""

    occurred_at: datetime
```

```python
# packages/arch-commons/src/commons/types/clock.py
from __future__ import annotations

from datetime import datetime
from typing import Protocol


class Clock(Protocol):
    def now(self) -> datetime: ...
```

- [ ] **Step 4: Run to verify it passes**

Run: `uv run --package arch-commons pytest packages/arch-commons/tests/types/test_events_clock.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add packages/arch-commons/src/commons/types/events.py packages/arch-commons/src/commons/types/clock.py \
        packages/arch-commons/tests/types/test_events_clock.py
git commit -m "$(cat <<'EOF'
feat: add commons.types.events (DomainEvent) and clock (Clock)

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01GEq9yHV4hbB35DxtL11UFL
EOF
)"
```

### Task 5: `commons.types.event_bus` + `commons.types.id_generator` — `EventBus`, `IdGenerator`

**Files:**
- Create: `packages/arch-commons/src/commons/types/event_bus.py`
- Create: `packages/arch-commons/src/commons/types/id_generator.py`
- Test: `packages/arch-commons/tests/types/test_event_bus_id_generator.py`

**Interfaces:**
- Consumes: `commons.types.events.DomainEvent` (Task 4).
- Produces: `EventBus.publish_all(events: Iterable[DomainEvent]) -> None` (spec Section 6.2's `self._bus.publish_all(...)`). `IdGenerator.new_id() -> str` (trade-off log row B: `IdGenerator` lives in `commons/types/` as a Protocol; a repository's own `next_identity()` method calls an injected `IdGenerator` internally — Task 23's template repository does exactly this).

- [ ] **Step 1: Write the failing test**

```python
# packages/arch-commons/tests/types/test_event_bus_id_generator.py
from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC, datetime


def test_given_an_event_bus_implementation__when_publish_all_called__then_no_error() -> None:
    from commons.types.event_bus import EventBus
    from commons.types.events import DomainEvent

    @dataclass(frozen=True)
    class Recorded:
        published: list[object]

        def publish_all(self, events: Iterable[DomainEvent]) -> None:
            self.published.extend(events)

    published: list[object] = []
    bus: EventBus = Recorded(published=published)

    @dataclass(frozen=True)
    class WidgetCreated:
        occurred_at: datetime

    bus.publish_all([WidgetCreated(occurred_at=datetime.now(UTC))])
    assert len(published) == 1


def test_given_an_id_generator_implementation__when_new_id_called__then_returns_a_string() -> None:
    from commons.types.id_generator import IdGenerator

    class FixedIdGenerator:
        def new_id(self) -> str:
            return "fixed-id"

    generator: IdGenerator = FixedIdGenerator()
    assert generator.new_id() == "fixed-id"
```

- [ ] **Step 2: Run to verify it fails**

Run: `uv run --package arch-commons pytest packages/arch-commons/tests/types/test_event_bus_id_generator.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'commons.types.event_bus'`

- [ ] **Step 3: Implement**

```python
# packages/arch-commons/src/commons/types/event_bus.py
from __future__ import annotations

from collections.abc import Iterable
from typing import Protocol

from commons.types.events import DomainEvent


class EventBus(Protocol):
    def publish_all(self, events: Iterable[DomainEvent]) -> None: ...
```

```python
# packages/arch-commons/src/commons/types/id_generator.py
from __future__ import annotations

from typing import Protocol


class IdGenerator(Protocol):
    def new_id(self) -> str: ...
```

- [ ] **Step 4: Run to verify it passes**

Run: `uv run --package arch-commons pytest packages/arch-commons/tests/types/test_event_bus_id_generator.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add packages/arch-commons/src/commons/types/event_bus.py packages/arch-commons/src/commons/types/id_generator.py \
        packages/arch-commons/tests/types/test_event_bus_id_generator.py
git commit -m "$(cat <<'EOF'
feat: add commons.types.event_bus (EventBus) and id_generator (IdGenerator)

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01GEq9yHV4hbB35DxtL11UFL
EOF
)"
```

### Task 6: `commons.types.unit_of_work` — the `UnitOfWork` Protocol

**Files:**
- Create: `packages/arch-commons/src/commons/types/unit_of_work.py`
- Test: `packages/arch-commons/tests/types/test_unit_of_work.py`

**Interfaces:**
- Consumes: `commons.types.events.DomainEvent` (Task 4).
- Produces: `UnitOfWork` — the exact Protocol from spec Section 7.2, verbatim: `__enter__`, `__exit__`, `commit`, `rollback`, `track`, `collect_new_events`.

- [ ] **Step 1: Write the failing test**

```python
# packages/arch-commons/tests/types/test_unit_of_work.py
from __future__ import annotations

from collections.abc import Iterable
from datetime import UTC, datetime


def test_given_a_unit_of_work_implementation__when_used_as_context_manager__then_matches_protocol() -> None:
    from commons.types.events import DomainEvent
    from commons.types.unit_of_work import UnitOfWork

    class Recording:
        def __init__(self) -> None:
            self.committed = False
            self.tracked: list[object] = []

        def __enter__(self) -> "Recording":
            return self

        def __exit__(self, *exc: object) -> None:
            pass

        def commit(self) -> None:
            self.committed = True

        def rollback(self) -> None:
            self.committed = False

        def track(self, aggregate: object) -> None:
            self.tracked.append(aggregate)

        def collect_new_events(self) -> Iterable[DomainEvent]:
            return []

    uow: UnitOfWork = Recording()
    with uow:
        uow.track(object())
        uow.commit()
    assert list(uow.collect_new_events()) == []
```

- [ ] **Step 2: Run to verify it fails**

Run: `uv run --package arch-commons pytest packages/arch-commons/tests/types/test_unit_of_work.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'commons.types.unit_of_work'`

- [ ] **Step 3: Implement**

```python
# packages/arch-commons/src/commons/types/unit_of_work.py
from __future__ import annotations

from collections.abc import Iterable
from typing import Protocol

from commons.types.events import DomainEvent


class UnitOfWork(Protocol):
    """Store-agnostic — owns the transaction and domain-event collection,
    says nothing about a specific database (spec Section 7.2)."""

    def __enter__(self) -> "UnitOfWork": ...
    def __exit__(self, *exc: object) -> None: ...
    def commit(self) -> None: ...
    def rollback(self) -> None: ...
    def track(self, aggregate: object) -> None: ...
    def collect_new_events(self) -> Iterable[DomainEvent]: ...
```

- [ ] **Step 4: Run to verify it passes**

Run: `uv run --package arch-commons pytest packages/arch-commons/tests/types/test_unit_of_work.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add packages/arch-commons/src/commons/types/unit_of_work.py packages/arch-commons/tests/types/test_unit_of_work.py
git commit -m "$(cat <<'EOF'
feat: add commons.types.unit_of_work (UnitOfWork Protocol)

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01GEq9yHV4hbB35DxtL11UFL
EOF
)"
```

### Task 7: `commons.infrastructure` leaf adapters — `InMemoryUnitOfWork`, `InMemoryEventBus`, `SystemClock`, `Uuid7IdGenerator`

**Files:**
- Create: `packages/arch-commons/src/commons/infrastructure/__init__.py`
- Create: `packages/arch-commons/src/commons/infrastructure/in_memory_unit_of_work.py`
- Create: `packages/arch-commons/src/commons/infrastructure/in_memory_event_bus.py`
- Create: `packages/arch-commons/src/commons/infrastructure/system_clock.py`
- Create: `packages/arch-commons/src/commons/infrastructure/uuid7_id_generator.py`
- Test: `packages/arch-commons/tests/infrastructure/test_leaf_adapters.py`

**Interfaces:**
- Consumes: `commons.types.events.DomainEvent`, `commons.types.clock.Clock`, `commons.types.id_generator.IdGenerator`, `commons.types.unit_of_work.UnitOfWork` (Tasks 4–6).
- Produces: four concrete adapters with no external dependency beyond the stdlib — the "ships alongside for tests" half of spec Section 7.2, plus the two other I/O ports (`Clock`, `IdGenerator`) a runnable example needs before any real broker/DB exists. `InMemoryUnitOfWork` tracks by `id(aggregate)`, drains events via the `pending_events` / `clear_pending_events()` convention (duck-typed, not a formal base class — trade-off log row E: "lean toward minimal base classes in commons/ + conventions elsewhere").

- [ ] **Step 1: Write the failing test**

```python
# packages/arch-commons/tests/infrastructure/test_leaf_adapters.py
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime


@dataclass
class _Widget:
    id: str
    pending_events: list[object] = field(default_factory=list)

    def clear_pending_events(self) -> None:
        self.pending_events.clear()


def test_given_committed_uow__when_collect_new_events__then_returns_tracked_pending_events() -> None:
    from commons.infrastructure.in_memory_unit_of_work import InMemoryUnitOfWork

    widget = _Widget(id="w-1")
    widget.pending_events.append("WidgetCreated")
    uow = InMemoryUnitOfWork()
    with uow:
        uow.track(widget)
        uow.commit()
    assert list(uow.collect_new_events()) == ["WidgetCreated"]


def test_given_uncommitted_uow__when_exit__then_rollback_clears_tracked() -> None:
    from commons.infrastructure.in_memory_unit_of_work import InMemoryUnitOfWork

    widget = _Widget(id="w-1")
    widget.pending_events.append("WidgetCreated")
    uow = InMemoryUnitOfWork()
    with uow:
        uow.track(widget)
        # no commit() -- __exit__ must roll back
    assert list(uow.collect_new_events()) == []


def test_given_in_memory_event_bus__when_publish_all__then_records_events() -> None:
    from commons.infrastructure.in_memory_event_bus import InMemoryEventBus

    bus = InMemoryEventBus()
    bus.publish_all(["WidgetCreated"])
    assert bus.published == ["WidgetCreated"]


def test_given_system_clock__when_now__then_returns_a_timezone_aware_datetime() -> None:
    from commons.infrastructure.system_clock import SystemClock

    now = SystemClock().now()
    assert isinstance(now, datetime)
    assert now.tzinfo is UTC


def test_given_uuid7_id_generator__when_new_id__then_returns_a_valid_version_7_uuid() -> None:
    from commons.infrastructure.uuid7_id_generator import Uuid7IdGenerator

    generator = Uuid7IdGenerator()
    new_id = generator.new_id()
    parsed = uuid.UUID(new_id)
    assert parsed.version == 7


def test_given_uuid7_id_generator__when_called_twice__then_ids_differ() -> None:
    from commons.infrastructure.uuid7_id_generator import Uuid7IdGenerator

    generator = Uuid7IdGenerator()
    assert generator.new_id() != generator.new_id()
```

- [ ] **Step 2: Run to verify it fails**

Run: `uv run --package arch-commons pytest packages/arch-commons/tests/infrastructure/test_leaf_adapters.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'commons.infrastructure'`

- [ ] **Step 3: Implement**

```python
# packages/arch-commons/src/commons/infrastructure/__init__.py
from __future__ import annotations
```

```python
# packages/arch-commons/src/commons/infrastructure/in_memory_unit_of_work.py
from __future__ import annotations

from collections.abc import Iterable

from commons.types.events import DomainEvent


class InMemoryUnitOfWork:
    """Dict-backed UnitOfWork for tests and template projects with no real
    store yet. Repositories call ``track()`` explicitly on every load and
    store -- there is no session to infer it from."""

    def __init__(self) -> None:
        self._tracked: dict[int, object] = {}
        self._committed = False

    def __enter__(self) -> "InMemoryUnitOfWork":
        self._committed = False
        return self

    def __exit__(self, *exc: object) -> None:
        if not self._committed:
            self.rollback()

    def commit(self) -> None:
        self._committed = True

    def rollback(self) -> None:
        self._tracked.clear()

    def track(self, aggregate: object) -> None:
        self._tracked[id(aggregate)] = aggregate

    def collect_new_events(self) -> Iterable[DomainEvent]:
        events: list[DomainEvent] = []
        for aggregate in self._tracked.values():
            pending = getattr(aggregate, "pending_events", None)
            if not pending:
                continue
            events.extend(pending)
            clear = getattr(aggregate, "clear_pending_events", None)
            if clear is not None:
                clear()
        return events
```

```python
# packages/arch-commons/src/commons/infrastructure/in_memory_event_bus.py
from __future__ import annotations

from collections.abc import Iterable

from commons.types.events import DomainEvent


class InMemoryEventBus:
    """No real broker wired yet -- records what was published, for tests and
    for template projects before a broker exists."""

    def __init__(self) -> None:
        self.published: list[DomainEvent] = []

    def publish_all(self, events: Iterable[DomainEvent]) -> None:
        self.published.extend(events)
```

```python
# packages/arch-commons/src/commons/infrastructure/system_clock.py
from __future__ import annotations

from datetime import UTC, datetime


class SystemClock:
    """The one place allowed to call ``datetime.now()`` -- domain/application
    never do (spec Section 5.1, ARCH-004); they take a ``Clock`` port instead."""

    def now(self) -> datetime:
        return datetime.now(UTC)
```

```python
# packages/arch-commons/src/commons/infrastructure/uuid7_id_generator.py
from __future__ import annotations

import os
import time
import uuid


class Uuid7IdGenerator:
    """UUIDv7 identifiers (spec Section 0: identifiers are application-generated,
    UUIDv7). Python's stdlib ``uuid`` module has no ``uuid7()`` before 3.14, so
    this implements RFC 9562's layout directly: a 48-bit millisecond timestamp,
    a 4-bit version, a 2-bit variant, and 74 random bits.
    """

    def new_id(self) -> str:
        timestamp_ms = int(time.time() * 1000)
        rand = os.urandom(10)
        time_bytes = timestamp_ms.to_bytes(6, "big")
        version_and_rand_a = ((0x7 << 12) | (int.from_bytes(rand[0:2], "big") & 0x0FFF)).to_bytes(
            2, "big"
        )
        variant_and_rand_b = bytes([0x80 | (rand[2] & 0x3F), *rand[3:10]])
        raw = time_bytes + version_and_rand_a + variant_and_rand_b
        return str(uuid.UUID(bytes=raw))
```

- [ ] **Step 4: Run to verify it passes**

Run: `uv run --package arch-commons pytest packages/arch-commons/tests/infrastructure/test_leaf_adapters.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add packages/arch-commons/src/commons/infrastructure/__init__.py \
        packages/arch-commons/src/commons/infrastructure/in_memory_unit_of_work.py \
        packages/arch-commons/src/commons/infrastructure/in_memory_event_bus.py \
        packages/arch-commons/src/commons/infrastructure/system_clock.py \
        packages/arch-commons/src/commons/infrastructure/uuid7_id_generator.py \
        packages/arch-commons/tests/infrastructure/test_leaf_adapters.py
git commit -m "$(cat <<'EOF'
feat: add commons.infrastructure leaf adapters (InMemoryUnitOfWork,
InMemoryEventBus, SystemClock, Uuid7IdGenerator)

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01GEq9yHV4hbB35DxtL11UFL
EOF
)"
```

### Task 8: `commons.infrastructure.sqlalchemy_unit_of_work` — the reference `UnitOfWork`

**Files:**
- Create: `packages/arch-commons/src/commons/infrastructure/sqlalchemy_unit_of_work.py`
- Test: `packages/arch-commons/tests/infrastructure/test_sqlalchemy_unit_of_work.py`

**Interfaces:**
- Consumes: `commons.types.events.DomainEvent` (Task 4). Requires the `sqlalchemy` extra (already in arch-commons's dev group from Task 1).
- Produces: `SqlAlchemyUnitOfWork(session_factory)` — the shipped reference implementation from spec Section 7.2. `track()` is a documented no-op: the session's own identity map already knows every object added or loaded through it (Percival & Gregory, *Architecture Patterns with Python*, ch. 6 — this exact "drain domain events from the session" pattern is where the design comes from, not an invented one).

- [ ] **Step 1: Write the failing test**

```python
# packages/arch-commons/tests/infrastructure/test_sqlalchemy_unit_of_work.py
from __future__ import annotations

from dataclasses import dataclass, field

import sqlalchemy as sa
from sqlalchemy.orm import registry, sessionmaker


@dataclass
class _Widget:
    id: str
    pending_events: list[object] = field(default_factory=list)

    def clear_pending_events(self) -> None:
        self.pending_events.clear()


def _session_factory() -> sessionmaker:  # type: ignore[type-arg]
    engine = sa.create_engine("sqlite:///:memory:")
    metadata = sa.MetaData()
    widgets = sa.Table(
        "widgets", metadata, sa.Column("id", sa.String, primary_key=True)
    )
    mapper_registry = registry(metadata=metadata)
    mapper_registry.map_imperatively(_Widget, widgets, properties={"pending_events": None})
    metadata.create_all(engine)
    return sessionmaker(bind=engine)


def test_given_added_widget__when_committed__then_collect_new_events_drains_it() -> None:
    from commons.infrastructure.sqlalchemy_unit_of_work import SqlAlchemyUnitOfWork

    uow = SqlAlchemyUnitOfWork(_session_factory())
    with uow:
        widget = _Widget(id="w-1")
        widget.pending_events.append("WidgetCreated")
        uow.session.add(widget)
        uow.commit()
    assert list(uow.collect_new_events()) == ["WidgetCreated"]


def test_given_uncommitted_change__when_exit__then_rollback_and_session_closed() -> None:
    from commons.infrastructure.sqlalchemy_unit_of_work import SqlAlchemyUnitOfWork

    uow = SqlAlchemyUnitOfWork(_session_factory())
    with uow:
        uow.session.add(_Widget(id="w-1"))
        # no commit() -- __exit__ must roll back
    assert uow.session.close.__self__ is uow.session  # session was closed, not left open
```

Note: SQLAlchemy's imperative mapping requires a plain attribute for `pending_events`, not a mapped column; `properties={"pending_events": None}` above is a test-fixture simplification (the real per-context `mapping.py` a generated project writes maps only persisted columns and leaves `pending_events` as an ordinary Python attribute the ORM never touches — this test fixture makes that explicit rather than mapping it).

- [ ] **Step 2: Run to verify it fails**

Run: `uv run --package arch-commons pytest packages/arch-commons/tests/infrastructure/test_sqlalchemy_unit_of_work.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'commons.infrastructure.sqlalchemy_unit_of_work'`

- [ ] **Step 3: Implement**

```python
# packages/arch-commons/src/commons/infrastructure/sqlalchemy_unit_of_work.py
from __future__ import annotations

from collections.abc import Iterable

from sqlalchemy.orm import Session, sessionmaker

from commons.types.events import DomainEvent


class SqlAlchemyUnitOfWork:
    """Reference UnitOfWork backed by a SQLAlchemy Session (spec Section 7.2).

    ``track()`` is a no-op: the session's own identity map already knows every
    object added to or loaded through it, so draining works off
    ``session.new | session.dirty | session.identity_map`` instead of an
    explicit tracked list.
    """

    def __init__(self, session_factory: sessionmaker) -> None:  # type: ignore[type-arg]
        self.session: Session = session_factory()
        self._committed = False

    def __enter__(self) -> "SqlAlchemyUnitOfWork":
        self._committed = False
        return self

    def __exit__(self, *exc: object) -> None:
        if not self._committed:
            self.rollback()
        self.session.close()

    def commit(self) -> None:
        self.session.commit()
        self._committed = True

    def rollback(self) -> None:
        self.session.rollback()

    def track(self, aggregate: object) -> None:
        """No-op: the session's identity map tracks membership implicitly."""

    def collect_new_events(self) -> Iterable[DomainEvent]:
        candidates: set[object] = set(self.session.new) | set(self.session.dirty)
        candidates |= set(self.session.identity_map.values())
        events: list[DomainEvent] = []
        for aggregate in candidates:
            pending = getattr(aggregate, "pending_events", None)
            if not pending:
                continue
            events.extend(pending)
            clear = getattr(aggregate, "clear_pending_events", None)
            if clear is not None:
                clear()
        return events
```

- [ ] **Step 4: Run to verify it passes**

Run: `uv run --package arch-commons pytest packages/arch-commons/tests/infrastructure/test_sqlalchemy_unit_of_work.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add packages/arch-commons/src/commons/infrastructure/sqlalchemy_unit_of_work.py \
        packages/arch-commons/tests/infrastructure/test_sqlalchemy_unit_of_work.py
git commit -m "$(cat <<'EOF'
feat: add commons.infrastructure.sqlalchemy_unit_of_work (reference UoW)

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01GEq9yHV4hbB35DxtL11UFL
EOF
)"
```

### Task 9: `commons.infrastructure.outbox` — transactional outbox machinery

**Files:**
- Create: `packages/arch-commons/src/commons/infrastructure/outbox.py`
- Test: `packages/arch-commons/tests/infrastructure/test_outbox.py`

**Interfaces:**
- Produces: `outbox_table` (SQLAlchemy Core `Table`), `record(session, event_type, payload, occurred_at, message_id) -> None` (insert in the caller's own open transaction — ARCH-036's "same transaction" requirement), `drain(session, publish, batch_size=100) -> int` (a separate process/transaction reads unpublished rows oldest-first and marks them published). Spec Section 7.3: "Machinery lives in `commons/infrastructure/outbox.py`" — this is the mandatory-when-guaranteed-delivery mechanism, not conditional scaffolding.

- [ ] **Step 1: Write the failing test**

```python
# packages/arch-commons/tests/infrastructure/test_outbox.py
from __future__ import annotations

from datetime import UTC, datetime

import sqlalchemy as sa
from sqlalchemy.orm import Session


def _session() -> Session:
    engine = sa.create_engine("sqlite:///:memory:")
    from commons.infrastructure.outbox import outbox_table

    outbox_table.metadata.create_all(engine)
    return Session(engine)


def test_given_recorded_message__when_drained__then_published_and_marked() -> None:
    from commons.infrastructure.outbox import drain, record

    session = _session()
    record(
        session,
        event_type="OrderCreated",
        payload='{"order_id": "o-1"}',
        occurred_at=datetime.now(UTC),
        message_id="m-1",
    )
    session.commit()

    published: list[tuple[str, str]] = []
    count = drain(session, publish=lambda event_type, payload: published.append((event_type, payload)))

    assert count == 1
    assert published == [("OrderCreated", '{"order_id": "o-1"}')]


def test_given_already_drained_message__when_drained_again__then_not_republished() -> None:
    from commons.infrastructure.outbox import drain, record

    session = _session()
    record(
        session,
        event_type="OrderCreated",
        payload="{}",
        occurred_at=datetime.now(UTC),
        message_id="m-1",
    )
    session.commit()
    drain(session, publish=lambda *_: None)

    second_count = drain(session, publish=lambda *_: None)
    assert second_count == 0
```

- [ ] **Step 2: Run to verify it fails**

Run: `uv run --package arch-commons pytest packages/arch-commons/tests/infrastructure/test_outbox.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'commons.infrastructure.outbox'`

- [ ] **Step 3: Implement**

```python
# packages/arch-commons/src/commons/infrastructure/outbox.py
from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime

from sqlalchemy import Column, DateTime, MetaData, String, Table, Text
from sqlalchemy.orm import Session

_metadata = MetaData()

outbox_table = Table(
    "outbox",
    _metadata,
    Column("id", String, primary_key=True),
    Column("event_type", String, nullable=False),
    Column("payload", Text, nullable=False),
    Column("occurred_at", DateTime, nullable=False),
    Column("published_at", DateTime, nullable=True),
)


def record(
    session: Session,
    *,
    event_type: str,
    payload: str,
    occurred_at: datetime,
    message_id: str,
) -> None:
    """Insert one outbox row in the CALLER's own open transaction (ARCH-036 --
    delivery-guaranteed integration events are written in the same transaction
    as the aggregate change; a separate process publishes them)."""
    session.execute(
        outbox_table.insert().values(
            id=message_id,
            event_type=event_type,
            payload=payload,
            occurred_at=occurred_at,
            published_at=None,
        )
    )


def drain(
    session: Session,
    publish: Callable[[str, str], None],
    batch_size: int = 100,
) -> int:
    """Publish unpublished rows oldest-first, marking each on success. Runs in
    a SEPARATE process/transaction from ``record()``."""
    rows = session.execute(
        outbox_table.select()
        .where(outbox_table.c.published_at.is_(None))
        .order_by(outbox_table.c.occurred_at)
        .limit(batch_size)
    ).all()
    count = 0
    for row in rows:
        publish(row.event_type, row.payload)
        session.execute(
            outbox_table.update()
            .where(outbox_table.c.id == row.id)
            .values(published_at=datetime.now(UTC))
        )
        count += 1
    session.commit()
    return count
```

- [ ] **Step 4: Run to verify it passes**

Run: `uv run --package arch-commons pytest packages/arch-commons/tests/infrastructure/test_outbox.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add packages/arch-commons/src/commons/infrastructure/outbox.py packages/arch-commons/tests/infrastructure/test_outbox.py
git commit -m "$(cat <<'EOF'
feat: add commons.infrastructure.outbox (transactional outbox, ARCH-036)

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01GEq9yHV4hbB35DxtL11UFL
EOF
)"
```

### Task 10: Fix `ImportContractsCheck` — ARCH-034/035 must still fire once `commons` is installed, not vendored

**Files:**
- Modify: `src/arch_standard/checks/import_contracts.py`
- Modify: `tests/checks/test_import_contracts.py`

**Interfaces:**
- Consumes: the real, installed `commons` package from Task 1 (now an `arch-standard` dev dependency via the workspace).
- Produces: `build_contracts(project)` keeps emitting the ARCH-034 and ARCH-035 contracts correctly for a project that depends on `arch-commons` as a real dependency instead of vendoring it under `src/commons/`.

**Why this is a real bug, not speculative hardening:** `build_contracts` currently gates both contracts on `(project.src / "commons").is_dir()` / `(project.src / "commons" / "types").is_dir()` — i.e. "is `commons/` physically inside this project's own `src/`?" That was correct while `commons/` was assumed vendored. Now that Task 1 makes `arch-commons` an installed, non-vendored dependency (exactly what spec Section 8.1 requires), every future generated project will have `commons` resolvable via `site-packages`, never under its own `src/` — so this gate would silently stop emitting ARCH-034/035 for every project built on this standard from here on. Two different fixes are needed because the two contracts play different roles for import-linter:

- **ARCH-034** (`commons.infrastructure` is a *forbidden target*, not a source): import-linter's `include_external_packages = True` (already set in `build_contracts`) means a forbidden contract's target does not need to be locally resolvable — grimp records it as an external graph node purely from parsing `from commons.infrastructure import X` in the source files under test. The disk check on `commons/` is simply unnecessary; drop it and gate only on `domain_app` (there being anything to forbid from).
- **ARCH-035** (`commons.types` is the contract's *source*): import-linter must actually parse what `commons.types` itself imports, which means it must be resolvable on `sys.path` in the interpreter running the check — vendored under `src/` (old layout) or installed as `arch-commons` (new layout, resolved via `importlib.util.find_spec` in-process, since `arch-standard check` always runs inside the target project's own environment where `arch-commons` would be installed).

- [ ] **Step 1: Write the failing test**

```python
# append to tests/checks/test_import_contracts.py
def test_given_domain_app_and_installed_commons_types__when_build_contracts__then_arch_035_contract_present(
    tmp_path: Path,
) -> None:
    """commons.types is NOT vendored under this project's src/ -- it resolves
    only because arch-commons is installed in the running interpreter (this
    repo's own dev environment, via the Task 1 workspace dependency)."""
    root = tmp_path / "proj"
    for rel in [
        "src/sales/orders/domain/model/order.py",
        "src/sales/orders/application/order_service.py",
    ]:
        f = root / rel
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text("", encoding="utf-8")
    assert not (root / "src" / "commons").exists()

    layout = ProjectLayout.detect(root)
    ini = build_contracts(layout)

    assert "ARCH-034" in ini
    assert "ARCH-035" in ini
```

- [ ] **Step 2: Run to verify it fails**

Run: `uv run pytest tests/checks/test_import_contracts.py -k installed_commons -v`
Expected: FAIL — `assert "ARCH-035" in ini` fails (the contract is not emitted, because `commons/types` doesn't exist under `root/src`).

- [ ] **Step 3: Implement**

```python
# src/arch_standard/checks/import_contracts.py — add near the top, with the other imports
import importlib.util
```

```python
# src/arch_standard/checks/import_contracts.py — add near _domain_application_modules
def _commons_types_importable(project: ProjectLayout) -> bool:
    """ARCH-035's *source* is commons.types itself, so import-linter must be
    able to parse it -- unlike ARCH-034's forbidden *target*, this is not
    covered by include_external_packages. True if commons/types is vendored
    under the project's own src/ (legacy/local-dev layout) or if commons.types
    is installed as the arch-commons dependency in the interpreter running
    this check."""
    if (project.src / "commons" / "types").is_dir():
        return True
    return importlib.util.find_spec("commons.types") is not None
```

```python
# src/arch_standard/checks/import_contracts.py — replace the two gates in build_contracts
    domain_app = _domain_application_modules(project)
    if domain_app:
        lines += [
            "[importlinter:contract:ARCH-034]",
            "name = ARCH-034 commons.infrastructure isolated from domain and application",
            "type = forbidden",
            "source_modules =",
            *domain_app,
            "forbidden_modules =",
            "    commons.infrastructure",
            "",
        ]

    if _commons_types_importable(project):
        lines += [
            "[importlinter:contract:ARCH-035]",
            "name = ARCH-035 commons.types framework-free",
            "type = forbidden",
            "source_modules =",
            "    commons.types",
            "forbidden_modules =",
            *(f"    {module}" for module in _FRAMEWORK_MODULES),
            "",
        ]
```

(This removes the old `if domain_app and (project.src / "commons").is_dir():` and `if (project.src / "commons" / "types").is_dir():` lines entirely — the `_roots()` helper is unchanged, since `commons`/`bootstrap` inclusion in `root_packages` is orthogonal to this fix.)

- [ ] **Step 4: Run to verify it passes**

Run: `uv run pytest tests/checks/test_import_contracts.py -v`
Expected: PASS (new test plus every existing `import_contracts` test, since the old vendored-`commons/` fixtures still satisfy `_commons_types_importable` via the disk-check branch)

- [ ] **Step 5: Commit**

```bash
git add src/arch_standard/checks/import_contracts.py tests/checks/test_import_contracts.py
git commit -m "$(cat <<'EOF'
fix: ARCH-034/035 detect an installed arch-commons, not just a vendored one

commons/ is no longer vendored under any project's src/ (Task 1). The old
disk-existence gate would have silently stopped emitting both contracts for
every project built on this standard from here on.

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01GEq9yHV4hbB35DxtL11UFL
EOF
)"
```

---

## Group B: the `.arch-standard` version stamp and drift notice

**Worked example first.** A project generated today stamps `standard-version = "0.1.0"`. Eighteen months from now this repo has shipped a `2.0.0` catalog with a newly-binding `MUST`. The project's own `arch-standard check` should say so — not fail the build (upgrading is the project's decision, spec Section 16.3), just make the gap visible.

### Task 11: `version_stamp.py` — parse the stamp, compute crossed majors

**Files:**
- Create: `src/arch_standard/version_stamp.py`
- Test: `tests/test_version_stamp.py`

**Interfaces:**
- Produces: `VersionStamp(standard_version: str, template_version: str)`, `read_stamp(root: Path) -> VersionStamp | None`, `parse_semver(version: str) -> tuple[int, int, int]`, `majors_crossed(stamp_version: str, running_version: str) -> list[int]`. Consumed by Task 12 (CLI drift notice) and Task 15 (compatibility bump comparison reuses `parse_semver`).

- [ ] **Step 1: Write the failing test**

```python
# tests/test_version_stamp.py
from __future__ import annotations

from pathlib import Path

from arch_standard.version_stamp import VersionStamp, majors_crossed, parse_semver, read_stamp


def test_given_no_stamp_file__when_read__then_returns_none(tmp_path: Path) -> None:
    assert read_stamp(tmp_path) is None


def test_given_stamp_file__when_read__then_returns_versions(tmp_path: Path) -> None:
    (tmp_path / ".arch-standard").write_text(
        'standard-version = "1.0.0"\ntemplate-version = "1.0.0"\n', encoding="utf-8"
    )
    assert read_stamp(tmp_path) == VersionStamp(standard_version="1.0.0", template_version="1.0.0")


def test_given_version_string__when_parsed__then_tuple_of_ints() -> None:
    assert parse_semver("1.2.3") == (1, 2, 3)


def test_given_stamp_ahead_of_or_equal_to_running__when_majors_crossed__then_empty() -> None:
    assert majors_crossed("2.0.0", "2.5.0") == []
    assert majors_crossed("2.0.0", "1.9.0") == []


def test_given_stamp_behind_running_by_two_majors__when_majors_crossed__then_lists_both() -> None:
    assert majors_crossed("0.1.0", "2.3.0") == [1, 2]
```

- [ ] **Step 2: Run to verify it fails**

Run: `uv run pytest tests/test_version_stamp.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'arch_standard.version_stamp'`

- [ ] **Step 3: Implement**

```python
# src/arch_standard/version_stamp.py
from __future__ import annotations

import tomllib
from dataclasses import dataclass
from pathlib import Path

_STAMP_FILENAME = ".arch-standard"


@dataclass(frozen=True)
class VersionStamp:
    standard_version: str
    template_version: str


def read_stamp(root: Path) -> VersionStamp | None:
    path = root / _STAMP_FILENAME
    if not path.is_file():
        return None
    data = tomllib.loads(path.read_text(encoding="utf-8"))
    return VersionStamp(
        standard_version=data["standard-version"],
        template_version=data["template-version"],
    )


def parse_semver(version: str) -> tuple[int, int, int]:
    major, minor, patch = version.split(".")
    return int(major), int(minor), int(patch)


def majors_crossed(stamp_version: str, running_version: str) -> list[int]:
    """Every major version boundary strictly between the stamp and the
    running catalog, inclusive of the running major. Empty when the project
    is current or ahead."""
    stamp_major = parse_semver(stamp_version)[0]
    running_major = parse_semver(running_version)[0]
    if running_major <= stamp_major:
        return []
    return list(range(stamp_major + 1, running_major + 1))
```

- [ ] **Step 4: Run to verify it passes**

Run: `uv run pytest tests/test_version_stamp.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/arch_standard/version_stamp.py tests/test_version_stamp.py
git commit -m "$(cat <<'EOF'
feat: add version_stamp (.arch-standard parsing, majors_crossed)

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01GEq9yHV4hbB35DxtL11UFL
EOF
)"
```

### Task 12: wire the drift notice into `arch-standard check`

**Files:**
- Modify: `src/arch_standard/cli.py`
- Test: `tests/test_cli_drift_notice.py`

**Interfaces:**
- Consumes: `version_stamp.read_stamp`, `version_stamp.majors_crossed` (Task 11).
- Produces: `_drift_notice(root: Path) -> str | None` in `cli.py`; `_run_check` prints it (non-failing) after the report when present.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_cli_drift_notice.py
from __future__ import annotations

from pathlib import Path

import pytest

from arch_standard.cli import main


def test_given_no_stamp__when_check__then_no_drift_notice_printed(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    exit_code = main(["check", str(tmp_path)])
    out = capsys.readouterr().out
    assert exit_code == 0
    assert "NOTICE" not in out


def test_given_stamp_two_majors_behind__when_check__then_notice_names_both_majors(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    (tmp_path / ".arch-standard").write_text(
        'standard-version = "0.1.0"\ntemplate-version = "0.1.0"\n', encoding="utf-8"
    )
    monkeypatch.setattr("arch_standard.cli._pkg_version", lambda _name: "2.3.0")

    exit_code = main(["check", str(tmp_path)])
    out = capsys.readouterr().out

    assert exit_code == 0
    assert "NOTICE" in out
    assert "v1" in out and "v2" in out


def test_given_stamp_current__when_check__then_no_drift_notice(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    (tmp_path / ".arch-standard").write_text(
        'standard-version = "0.1.0"\ntemplate-version = "0.1.0"\n', encoding="utf-8"
    )
    monkeypatch.setattr("arch_standard.cli._pkg_version", lambda _name: "0.1.0")

    exit_code = main(["check", str(tmp_path)])
    out = capsys.readouterr().out

    assert exit_code == 0
    assert "NOTICE" not in out
```

- [ ] **Step 2: Run to verify it fails**

Run: `uv run pytest tests/test_cli_drift_notice.py -v`
Expected: FAIL — the two majors-behind cases fail (no notice is printed yet); the `monkeypatch.setattr("arch_standard.cli._pkg_version", ...)` calls also fail with `AttributeError` since `_pkg_version` does not exist yet.

- [ ] **Step 3: Implement**

```python
# src/arch_standard/cli.py — add imports
from importlib.metadata import version as _pkg_version

from arch_standard.version_stamp import majors_crossed, read_stamp
```

```python
# src/arch_standard/cli.py — new helper, above _run_check
def _drift_notice(root: Path) -> str | None:
    stamp = read_stamp(root)
    if stamp is None:
        return None
    running = _pkg_version("arch-standard")
    crossed = majors_crossed(stamp.standard_version, running)
    if not crossed:
        return None
    crossed_str = ", ".join(f"v{m}" for m in crossed)
    return (
        f"NOTICE: project is stamped standard-version={stamp.standard_version}, "
        f"running arch-standard {running} -- crossed major {crossed_str}. "
        "Upgrading the stamp is your decision; this does not fail the build."
    )
```

```python
# src/arch_standard/cli.py — in _run_check, right before "return report.exit_code(catalog)"
    notice = _drift_notice(root)
    if notice is not None:
        print(notice)
    return report.exit_code(catalog)
```

- [ ] **Step 4: Run to verify it passes**

Run: `uv run pytest tests/test_cli_drift_notice.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/arch_standard/cli.py tests/test_cli_drift_notice.py
git commit -m "$(cat <<'EOF'
feat: print a non-failing drift notice when .arch-standard is behind

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01GEq9yHV4hbB35DxtL11UFL
EOF
)"
```

---

## Group C: the rule-catalog compatibility policy — enforced, not just documented

**Worked example first.** Today's catalog (version `0.1.0`, frozen as a snapshot in Task 13) has ARCH-013 (`No dependency cycles between contexts`) at `SHOULD`. Suppose a future edit promotes it straight to `MUST` while only bumping the package to `0.2.0` (a minor). That is exactly the violation spec Section 16.3 exists to prevent — a `MUST` that never had a `SHOULD` warning window, landing without the major bump that would make it visible as a breaking change. This group builds the tool that catches it, and proves it also passes the *sanctioned* version of the same promotion (`SHOULD` in a minor, then `MUST` in the next major).

### Task 13: `release/snapshot.py` — freeze a catalog version, and the `release-snapshot` command

**Files:**
- Create: `src/arch_standard/release/__init__.py`
- Create: `src/arch_standard/release/snapshot.py`
- Create: `rules/.released/0.1.0/*.yaml` (copies of the current `rules/*.yaml`)
- Modify: `src/arch_standard/cli.py`
- Test: `tests/release/test_snapshot.py`

**Interfaces:**
- Produces: `write_snapshot(rules_dir: Path, version: str) -> Path`, `list_snapshot_versions(rules_dir: Path) -> list[str]`, `latest_snapshot_version(rules_dir: Path) -> str | None`. CLI: `arch-standard release-snapshot <version>` (operates on `Path.cwd() / "rules"`). Consumed by Tasks 14–19.

- [ ] **Step 1: Write the failing test**

```python
# tests/release/test_snapshot.py
from __future__ import annotations

from pathlib import Path

from arch_standard.release.snapshot import list_snapshot_versions, latest_snapshot_version, write_snapshot


def _make_rules_dir(tmp_path: Path) -> Path:
    rules_dir = tmp_path / "rules"
    rules_dir.mkdir()
    (rules_dir / "example.yaml").write_text("rules: []\n", encoding="utf-8")
    return rules_dir


def test_given_rules_dir__when_write_snapshot__then_copies_yaml_files(tmp_path: Path) -> None:
    rules_dir = _make_rules_dir(tmp_path)
    dest = write_snapshot(rules_dir, "1.0.0")
    assert dest == rules_dir / ".released" / "1.0.0"
    assert (dest / "example.yaml").read_text(encoding="utf-8") == "rules: []\n"


def test_given_existing_snapshot__when_write_snapshot_again__then_raises(tmp_path: Path) -> None:
    rules_dir = _make_rules_dir(tmp_path)
    write_snapshot(rules_dir, "1.0.0")
    try:
        write_snapshot(rules_dir, "1.0.0")
        raise AssertionError("expected FileExistsError")
    except FileExistsError:
        pass


def test_given_multiple_snapshots__when_listed__then_semver_sorted(tmp_path: Path) -> None:
    rules_dir = _make_rules_dir(tmp_path)
    write_snapshot(rules_dir, "1.10.0")
    write_snapshot(rules_dir, "1.2.0")
    write_snapshot(rules_dir, "2.0.0")
    assert list_snapshot_versions(rules_dir) == ["1.2.0", "1.10.0", "2.0.0"]
    assert latest_snapshot_version(rules_dir) == "2.0.0"


def test_given_no_snapshots__when_latest__then_none(tmp_path: Path) -> None:
    rules_dir = _make_rules_dir(tmp_path)
    assert latest_snapshot_version(rules_dir) is None
```

- [ ] **Step 2: Run to verify it fails**

Run: `uv run pytest tests/release/test_snapshot.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'arch_standard.release'`

- [ ] **Step 3: Implement**

```python
# src/arch_standard/release/__init__.py
from __future__ import annotations
```

```python
# src/arch_standard/release/snapshot.py
from __future__ import annotations

import shutil
from pathlib import Path

from arch_standard.version_stamp import parse_semver

_RELEASED_DIRNAME = ".released"


def snapshot_dir(rules_dir: Path, version: str) -> Path:
    return rules_dir / _RELEASED_DIRNAME / version


def write_snapshot(rules_dir: Path, version: str) -> Path:
    """Copy every rule YAML at rules_dir into rules_dir/.released/<version>/,
    freezing that version's catalog for future compatibility/changelog diffs."""
    dest = snapshot_dir(rules_dir, version)
    if dest.exists():
        raise FileExistsError(f"snapshot {version} already exists at {dest}")
    dest.mkdir(parents=True)
    for path in sorted(rules_dir.glob("*.yaml")):
        shutil.copy2(path, dest / path.name)
    return dest


def list_snapshot_versions(rules_dir: Path) -> list[str]:
    released = rules_dir / _RELEASED_DIRNAME
    if not released.is_dir():
        return []
    return sorted(
        (p.name for p in released.iterdir() if p.is_dir()),
        key=parse_semver,
    )


def latest_snapshot_version(rules_dir: Path) -> str | None:
    versions = list_snapshot_versions(rules_dir)
    return versions[-1] if versions else None
```

Now freeze the repo's real, current catalog as the `0.1.0` baseline (matches `[project].version` in the root `pyproject.toml` today):

Run: `uv run python -c "from pathlib import Path; from arch_standard.release.snapshot import write_snapshot; write_snapshot(Path('rules'), '0.1.0')"`

Wire the CLI subcommand:

```python
# src/arch_standard/cli.py — in _build_parser, after the "docs" subparser
    release_snapshot = sub.add_parser(
        "release-snapshot", help="freeze the current rules/ catalog as a released version"
    )
    release_snapshot.add_argument("version", help="the version being released, e.g. 1.1.0")
```

```python
# src/arch_standard/cli.py — new function
def _run_release_snapshot(version: str) -> int:
    from arch_standard.release.snapshot import write_snapshot

    dest = write_snapshot(Path.cwd() / "rules", version)
    print(f"wrote snapshot {dest}")
    return 0
```

```python
# src/arch_standard/cli.py — main(), extend the whitelist and dispatch
    if argv[0] not in {"check", "docs", "release-snapshot", "-h", "--help"}:
        parser.print_usage()
        return 2
    args = parser.parse_args(argv)
    if args.command == "check":
        return _run_check(args.path, core=args.core)
    if args.command == "docs":
        return _run_docs(check=args.check)
    if args.command == "release-snapshot":
        return _run_release_snapshot(args.version)
    return 0
```

- [ ] **Step 4: Run to verify it passes**

Run: `uv run pytest tests/release/test_snapshot.py -v`
Expected: PASS

Run: `uv run arch-standard release-snapshot --help` to confirm the subcommand parses.

- [ ] **Step 5: Commit**

```bash
git add src/arch_standard/release/__init__.py src/arch_standard/release/snapshot.py \
        src/arch_standard/cli.py tests/release/test_snapshot.py rules/.released/0.1.0
git commit -m "$(cat <<'EOF'
feat: add release snapshot mechanism and freeze the 0.1.0 catalog baseline

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01GEq9yHV4hbB35DxtL11UFL
EOF
)"
```

### Task 14: `release/diff.py` — classify what changed between two catalogs

**Files:**
- Create: `src/arch_standard/release/diff.py`
- Test: `tests/release/test_diff.py`

**Interfaces:**
- Consumes: `arch_standard.rules.catalog.Catalog`, `arch_standard.rules.model.Level`.
- Produces: `ChangeKind` (`ADDED | REMOVED | LEVEL_CHANGED | CONTENT_CHANGED`), `RuleChange(rule_id, kind, old_level=None, new_level=None)`, `diff_catalogs(old: Catalog, new: Catalog) -> list[RuleChange]`. Consumed by Task 15 (compatibility) and Task 17 (changelog).

- [ ] **Step 1: Write the failing test**

```python
# tests/release/test_diff.py
from __future__ import annotations

from arch_standard.release.diff import ChangeKind, diff_catalogs
from arch_standard.rules.catalog import Catalog
from arch_standard.rules.model import Automation, Level, Rule, ValidationSpec


def _rule(rule_id: str, level: Level, description: str = "desc") -> Rule:
    return Rule(
        id=rule_id,
        name=f"name for {rule_id}",
        level=level,
        automation=Automation.MANUAL,
        category="example",
        description=description,
        rationale="rationale",
        correct="ok",
        incorrect="bad",
        validation=ValidationSpec(tool="review"),
    )


def test_given_new_rule_added__when_diffed__then_reports_added() -> None:
    old = Catalog([])
    new = Catalog([_rule("ARCH-900", Level.SHOULD)])
    changes = diff_catalogs(old, new)
    assert changes == [_rule_change("ARCH-900", ChangeKind.ADDED, new_level=Level.SHOULD)]


def test_given_rule_removed__when_diffed__then_reports_removed() -> None:
    old = Catalog([_rule("ARCH-900", Level.SHOULD)])
    new = Catalog([])
    changes = diff_catalogs(old, new)
    assert changes == [_rule_change("ARCH-900", ChangeKind.REMOVED, old_level=Level.SHOULD)]


def test_given_level_raised__when_diffed__then_reports_level_changed() -> None:
    old = Catalog([_rule("ARCH-900", Level.SHOULD)])
    new = Catalog([_rule("ARCH-900", Level.MUST)])
    changes = diff_catalogs(old, new)
    assert changes == [
        _rule_change("ARCH-900", ChangeKind.LEVEL_CHANGED, old_level=Level.SHOULD, new_level=Level.MUST)
    ]


def test_given_only_description_changed__when_diffed__then_reports_content_changed() -> None:
    old = Catalog([_rule("ARCH-900", Level.SHOULD, description="old wording")])
    new = Catalog([_rule("ARCH-900", Level.SHOULD, description="new wording")])
    changes = diff_catalogs(old, new)
    assert changes == [
        _rule_change("ARCH-900", ChangeKind.CONTENT_CHANGED, old_level=Level.SHOULD, new_level=Level.SHOULD)
    ]


def test_given_identical_catalogs__when_diffed__then_no_changes() -> None:
    old = Catalog([_rule("ARCH-900", Level.SHOULD)])
    new = Catalog([_rule("ARCH-900", Level.SHOULD)])
    assert diff_catalogs(old, new) == []


def _rule_change(
    rule_id: str,
    kind: ChangeKind,
    old_level: Level | None = None,
    new_level: Level | None = None,
) -> object:
    from arch_standard.release.diff import RuleChange

    return RuleChange(rule_id=rule_id, kind=kind, old_level=old_level, new_level=new_level)
```

- [ ] **Step 2: Run to verify it fails**

Run: `uv run pytest tests/release/test_diff.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'arch_standard.release.diff'`

- [ ] **Step 3: Implement**

```python
# src/arch_standard/release/diff.py
from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from arch_standard.rules.catalog import Catalog
from arch_standard.rules.model import Level


class ChangeKind(StrEnum):
    ADDED = "added"
    REMOVED = "removed"
    LEVEL_CHANGED = "level_changed"
    CONTENT_CHANGED = "content_changed"


@dataclass(frozen=True)
class RuleChange:
    rule_id: str
    kind: ChangeKind
    old_level: Level | None = None
    new_level: Level | None = None


def diff_catalogs(old: Catalog, new: Catalog) -> list[RuleChange]:
    old_ids = {rule.id for rule in old}
    new_ids = {rule.id for rule in new}
    changes: list[RuleChange] = []

    for rule_id in sorted(new_ids - old_ids):
        changes.append(RuleChange(rule_id=rule_id, kind=ChangeKind.ADDED, new_level=new.get(rule_id).level))

    for rule_id in sorted(old_ids - new_ids):
        changes.append(RuleChange(rule_id=rule_id, kind=ChangeKind.REMOVED, old_level=old.get(rule_id).level))

    for rule_id in sorted(old_ids & new_ids):
        old_rule, new_rule = old.get(rule_id), new.get(rule_id)
        if old_rule.level != new_rule.level:
            changes.append(
                RuleChange(
                    rule_id=rule_id,
                    kind=ChangeKind.LEVEL_CHANGED,
                    old_level=old_rule.level,
                    new_level=new_rule.level,
                )
            )
        elif old_rule != new_rule:
            changes.append(
                RuleChange(
                    rule_id=rule_id,
                    kind=ChangeKind.CONTENT_CHANGED,
                    old_level=old_rule.level,
                    new_level=new_rule.level,
                )
            )

    return changes
```

- [ ] **Step 4: Run to verify it passes**

Run: `uv run pytest tests/release/test_diff.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/arch_standard/release/diff.py tests/release/test_diff.py
git commit -m "$(cat <<'EOF'
feat: add release.diff (catalog-to-catalog change classification)

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01GEq9yHV4hbB35DxtL11UFL
EOF
)"
```

### Task 15: `release/compatibility.py` — required bump, actual bump, unsanctioned `MUST` promotions

**Files:**
- Create: `src/arch_standard/release/compatibility.py`
- Test: `tests/release/test_compatibility.py`

**Interfaces:**
- Consumes: `arch_standard.release.diff.{ChangeKind, RuleChange}` (Task 14), `arch_standard.version_stamp.parse_semver` (Task 11).
- Produces: `required_bump(changes) -> str` (`"major" | "minor" | "patch" | "none"`), `actual_bump(old_version, new_version) -> str`, `bump_satisfies(actual, required) -> bool`, `find_unsanctioned_must_promotions(changes) -> list[str]`.

- [ ] **Step 1: Write the failing test**

```python
# tests/release/test_compatibility.py
from __future__ import annotations

from arch_standard.release.compatibility import (
    actual_bump,
    bump_satisfies,
    find_unsanctioned_must_promotions,
    required_bump,
)
from arch_standard.release.diff import ChangeKind, RuleChange
from arch_standard.rules.model import Level


def test_given_should_promoted_to_must__when_required_bump__then_major() -> None:
    changes = [
        RuleChange(
            rule_id="ARCH-900", kind=ChangeKind.LEVEL_CHANGED, old_level=Level.SHOULD, new_level=Level.MUST
        )
    ]
    assert required_bump(changes) == "major"


def test_given_new_should_rule_added__when_required_bump__then_minor() -> None:
    changes = [RuleChange(rule_id="ARCH-900", kind=ChangeKind.ADDED, new_level=Level.SHOULD)]
    assert required_bump(changes) == "minor"


def test_given_only_wording_changed__when_required_bump__then_patch() -> None:
    changes = [
        RuleChange(
            rule_id="ARCH-900",
            kind=ChangeKind.CONTENT_CHANGED,
            old_level=Level.SHOULD,
            new_level=Level.SHOULD,
        )
    ]
    assert required_bump(changes) == "patch"


def test_given_no_changes__when_required_bump__then_none() -> None:
    assert required_bump([]) == "none"


def test_given_actual_and_required_bumps__when_compared__then_satisfies_only_when_at_least_as_large() -> None:
    assert bump_satisfies("major", "major")
    assert bump_satisfies("major", "minor")
    assert not bump_satisfies("minor", "major")
    assert not bump_satisfies("patch", "minor")


def test_given_version_pair__when_actual_bump__then_classified() -> None:
    assert actual_bump("1.1.0", "2.0.0") == "major"
    assert actual_bump("1.1.0", "1.2.0") == "minor"
    assert actual_bump("1.1.0", "1.1.1") == "patch"
    assert actual_bump("1.1.0", "1.1.0") == "none"


def test_given_should_promoted_to_must__when_checked_for_sanction__then_no_violation() -> None:
    """The sanctioned path: SHOULD in the preceding snapshot, MUST now."""
    changes = [
        RuleChange(
            rule_id="ARCH-900", kind=ChangeKind.LEVEL_CHANGED, old_level=Level.SHOULD, new_level=Level.MUST
        )
    ]
    assert find_unsanctioned_must_promotions(changes) == []


def test_given_new_rule_landing_directly_as_must__when_checked__then_violation() -> None:
    changes = [RuleChange(rule_id="ARCH-901", kind=ChangeKind.ADDED, new_level=Level.MUST)]
    assert find_unsanctioned_must_promotions(changes) == ["ARCH-901"]


def test_given_may_jumping_straight_to_must__when_checked__then_violation() -> None:
    changes = [
        RuleChange(
            rule_id="ARCH-902", kind=ChangeKind.LEVEL_CHANGED, old_level=Level.MAY, new_level=Level.MUST
        )
    ]
    assert find_unsanctioned_must_promotions(changes) == ["ARCH-902"]
```

- [ ] **Step 2: Run to verify it fails**

Run: `uv run pytest tests/release/test_compatibility.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'arch_standard.release.compatibility'`

- [ ] **Step 3: Implement**

```python
# src/arch_standard/release/compatibility.py
from __future__ import annotations

from arch_standard.release.diff import ChangeKind, RuleChange
from arch_standard.rules.model import Level
from arch_standard.version_stamp import parse_semver

_BINDING = (Level.MUST, Level.MUST_CONDITIONAL)
_ORDER = {"none": 0, "patch": 1, "minor": 2, "major": 3}


def required_bump(changes: list[RuleChange]) -> str:
    """The minimum version-bump kind (spec Section 16.3) implied by a diff."""
    if any(
        change.kind in (ChangeKind.ADDED, ChangeKind.LEVEL_CHANGED) and change.new_level in _BINDING
        for change in changes
    ):
        return "major"
    if any(change.kind in (ChangeKind.ADDED, ChangeKind.LEVEL_CHANGED) for change in changes):
        return "minor"
    if changes:
        return "patch"
    return "none"


def actual_bump(old_version: str, new_version: str) -> str:
    old_major, old_minor, old_patch = parse_semver(old_version)
    new_major, new_minor, new_patch = parse_semver(new_version)
    if new_major != old_major:
        return "major"
    if new_minor != old_minor:
        return "minor"
    if new_patch != old_patch:
        return "patch"
    return "none"


def bump_satisfies(actual: str, required: str) -> bool:
    return _ORDER[actual] >= _ORDER[required]


def find_unsanctioned_must_promotions(changes: list[RuleChange]) -> list[str]:
    """A rule must never jump straight to MUST/MUST* -- it must have been
    SHOULD in the immediately preceding released snapshot (spec Section
    16.3: 'a new MUST never lands directly'). Returns the offending rule ids."""
    violations: list[str] = []
    for change in changes:
        if change.new_level not in _BINDING:
            continue
        if change.kind == ChangeKind.LEVEL_CHANGED and change.old_level is Level.SHOULD:
            continue  # SHOULD -> MUST is exactly the sanctioned promotion
        violations.append(change.rule_id)
    return violations
```

- [ ] **Step 4: Run to verify it passes**

Run: `uv run pytest tests/release/test_compatibility.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/arch_standard/release/compatibility.py tests/release/test_compatibility.py
git commit -m "$(cat <<'EOF'
feat: add release.compatibility (bump classification, MUST-promotion guard)

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01GEq9yHV4hbB35DxtL11UFL
EOF
)"
```

### Task 16: `arch-standard release-check` — wire it end to end

**Files:**
- Modify: `src/arch_standard/cli.py`
- Test: `tests/release/test_release_check_cli.py`

**Interfaces:**
- Consumes: `release.snapshot.{latest_snapshot_version, snapshot_dir}`, `release.diff.diff_catalogs`, `release.compatibility.{required_bump, actual_bump, bump_satisfies, find_unsanctioned_must_promotions}`, `rules.catalog.Catalog`.
- Produces: `arch-standard release-check --version X.Y.Z [--rules-dir PATH]` — loads the latest snapshot as "old", the live `rules/` tree as "new", diffs them, and fails (exit 1) if there is an unsanctioned `MUST` promotion or the requested version doesn't bump enough; otherwise prints a summary and exits 0.

- [ ] **Step 1: Write the failing test**

```python
# tests/release/test_release_check_cli.py
from __future__ import annotations

from pathlib import Path

import pytest

from arch_standard.cli import main

_RULE_TEMPLATE = """
rules:
  - id: ARCH-900
    name: example rule
    level: {level}
    automation: manual
    category: example
    description: an example rule for release-check testing
    rationale: exercises the compatibility checker end to end
    correct: |
      pass
    incorrect: |
      fail
    validation:
      tool: review
"""


def _write_rules(path: Path, level: str) -> None:
    path.mkdir(parents=True, exist_ok=True)
    (path / "example.yaml").write_text(_RULE_TEMPLATE.format(level=level), encoding="utf-8")


def test_given_sanctioned_should_to_must_promotion_with_major_bump__when_release_check__then_passes(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    rules_dir = tmp_path / "rules"
    _write_rules(rules_dir / ".released" / "1.1.0", level="SHOULD")
    _write_rules(rules_dir, level="MUST")

    exit_code = main(["release-check", "--version", "2.0.0", "--rules-dir", str(rules_dir)])
    assert exit_code == 0
    assert "OK" in capsys.readouterr().out


def test_given_unsanctioned_must_promotion__when_release_check__then_fails(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    rules_dir = tmp_path / "rules"
    _write_rules(rules_dir / ".released" / "1.1.0", level="MAY")
    _write_rules(rules_dir, level="MUST")

    exit_code = main(["release-check", "--version", "2.0.0", "--rules-dir", str(rules_dir)])
    assert exit_code == 1
    assert "ARCH-900" in capsys.readouterr().out


def test_given_must_promotion_with_only_minor_bump_requested__when_release_check__then_fails(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    rules_dir = tmp_path / "rules"
    _write_rules(rules_dir / ".released" / "1.1.0", level="SHOULD")
    _write_rules(rules_dir, level="MUST")

    exit_code = main(["release-check", "--version", "1.2.0", "--rules-dir", str(rules_dir)])
    assert exit_code == 1
    assert "requires at least a major bump" in capsys.readouterr().out
```

- [ ] **Step 2: Run to verify it fails**

Run: `uv run pytest tests/release/test_release_check_cli.py -v`
Expected: FAIL — `argparse` rejects the `release-check` command (unknown), or `main` returns `2` from the argv whitelist check.

- [ ] **Step 3: Implement**

```python
# src/arch_standard/cli.py — in _build_parser, after release_snapshot
    release_check = sub.add_parser(
        "release-check", help="verify a pending catalog change against the compatibility policy"
    )
    release_check.add_argument("--version", required=True, help="the version being released")
    release_check.add_argument("--rules-dir", default=None, help="rules dir (default: ./rules)")
```

```python
# src/arch_standard/cli.py — new function
def _run_release_check(version: str, rules_dir_arg: str | None) -> int:
    from arch_standard.release.compatibility import (
        actual_bump,
        bump_satisfies,
        find_unsanctioned_must_promotions,
        required_bump,
    )
    from arch_standard.release.diff import diff_catalogs
    from arch_standard.release.snapshot import latest_snapshot_version, snapshot_dir

    rules_dir = Path(rules_dir_arg) if rules_dir_arg else Path.cwd() / "rules"
    previous = latest_snapshot_version(rules_dir)
    if previous is None:
        print("no released snapshot to compare against -- run `arch-standard release-snapshot` first")
        return 1

    old_catalog = Catalog.load(snapshot_dir(rules_dir, previous))
    new_catalog = Catalog.load(rules_dir)
    changes = diff_catalogs(old_catalog, new_catalog)

    violations = find_unsanctioned_must_promotions(changes)
    if violations:
        for rule_id in violations:
            print(f"{rule_id} FAIL  jumps to MUST/MUST* without being SHOULD in {previous}")
        return 1

    required = required_bump(changes)
    actual = actual_bump(previous, version)
    if not bump_satisfies(actual, required):
        print(
            f"FAIL  {previous} -> {version} is a {actual} bump, but this diff "
            f"requires at least a {required} bump"
        )
        return 1

    print(f"OK  {previous} -> {version} ({actual} bump, {len(changes)} rule change(s))")
    return 0
```

```python
# src/arch_standard/cli.py — main(), extend the whitelist and dispatch
    if argv[0] not in {"check", "docs", "release-snapshot", "release-check", "-h", "--help"}:
        parser.print_usage()
        return 2
    args = parser.parse_args(argv)
    if args.command == "check":
        return _run_check(args.path, core=args.core)
    if args.command == "docs":
        return _run_docs(check=args.check)
    if args.command == "release-snapshot":
        return _run_release_snapshot(args.version)
    if args.command == "release-check":
        return _run_release_check(args.version, args.rules_dir)
    return 0
```

- [ ] **Step 4: Run to verify it passes**

Run: `uv run pytest tests/release/test_release_check_cli.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/arch_standard/cli.py tests/release/test_release_check_cli.py
git commit -m "$(cat <<'EOF'
feat: add arch-standard release-check (enforces the compatibility policy)

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01GEq9yHV4hbB35DxtL11UFL
EOF
)"
```

---

## Group D: CHANGELOG tooling

**Worked example first.** Reusing Task 16's own worked example: `ARCH-900` goes `SHOULD` (in the `1.1.0` snapshot) to `MUST` (in a new `2.0.0`). Spec Section 16.3: "for a major, the migration notes for each newly-binding `MUST`" — this group renders that changelog entry, and refuses to produce one for a `MUST` promotion with no migration notes supplied.

### Task 17: `release/changelog.py` — render one version's entry

**Files:**
- Create: `src/arch_standard/release/changelog.py`
- Test: `tests/release/test_changelog.py`

**Interfaces:**
- Consumes: `arch_standard.release.diff.{ChangeKind, RuleChange}` (Task 14), `arch_standard.rules.catalog.Catalog`.
- Produces: `render_changelog_entry(version: str, old: Catalog, new: Catalog, changes: list[RuleChange], migration_notes: str | None) -> str`.

**Design decision (simpler option, chosen deliberately):** migration notes are supplied by the release operator as free text at release time, not as a new field on `Rule`. Section 16.3 only requires migration notes exist *per newly-binding MUST*, which happens at most a handful of times per major — adding a versioned `migration_notes` field to every rule's YAML schema for an event that rare is exactly the kind of speculative schema growth this project avoids elsewhere; a CLI-supplied string (Task 18) keeps `rules/model.py` untouched.

- [ ] **Step 1: Write the failing test**

```python
# tests/release/test_changelog.py
from __future__ import annotations

from arch_standard.release.changelog import render_changelog_entry
from arch_standard.release.diff import ChangeKind, RuleChange
from arch_standard.rules.catalog import Catalog
from arch_standard.rules.model import Automation, Level, Rule, ValidationSpec


def _rule(rule_id: str, level: Level, name: str = "example rule") -> Rule:
    return Rule(
        id=rule_id,
        name=name,
        level=level,
        automation=Automation.MANUAL,
        category="example",
        description="desc",
        rationale="rationale",
        correct="ok",
        incorrect="bad",
        validation=ValidationSpec(tool="review"),
    )


def test_given_added_and_removed_rules__when_rendered__then_both_sections_present() -> None:
    old = Catalog([_rule("ARCH-800", Level.SHOULD, name="retired rule")])
    new = Catalog([_rule("ARCH-900", Level.SHOULD, name="new rule")])
    changes = [
        RuleChange(rule_id="ARCH-900", kind=ChangeKind.ADDED, new_level=Level.SHOULD),
        RuleChange(rule_id="ARCH-800", kind=ChangeKind.REMOVED, old_level=Level.SHOULD),
    ]

    entry = render_changelog_entry("1.1.0", old, new, changes, migration_notes=None)

    assert "## 1.1.0" in entry
    assert "### Added" in entry and "ARCH-900" in entry and "new rule" in entry
    assert "### Removed" in entry and "ARCH-800" in entry and "retired rule" in entry


def test_given_must_promotion_with_migration_notes__when_rendered__then_notes_included() -> None:
    old = Catalog([_rule("ARCH-900", Level.SHOULD)])
    new = Catalog([_rule("ARCH-900", Level.MUST)])
    changes = [
        RuleChange(rule_id="ARCH-900", kind=ChangeKind.LEVEL_CHANGED, old_level=Level.SHOULD, new_level=Level.MUST)
    ]

    entry = render_changelog_entry(
        "2.0.0", old, new, changes, migration_notes="Fix any remaining ARCH-900 warnings before upgrading."
    )

    assert "### Changed" in entry
    assert "ARCH-900" in entry and "SHOULD -> MUST" in entry
    assert "#### Migration notes" in entry
    assert "Fix any remaining ARCH-900 warnings" in entry
```

- [ ] **Step 2: Run to verify it fails**

Run: `uv run pytest tests/release/test_changelog.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'arch_standard.release.changelog'`

- [ ] **Step 3: Implement**

```python
# src/arch_standard/release/changelog.py
from __future__ import annotations

from arch_standard.release.diff import ChangeKind, RuleChange
from arch_standard.rules.catalog import Catalog


def render_changelog_entry(
    version: str,
    old: Catalog,
    new: Catalog,
    changes: list[RuleChange],
    migration_notes: str | None,
) -> str:
    added = [c for c in changes if c.kind == ChangeKind.ADDED]
    removed = [c for c in changes if c.kind == ChangeKind.REMOVED]
    level_changed = [c for c in changes if c.kind == ChangeKind.LEVEL_CHANGED]
    content_changed = [c for c in changes if c.kind == ChangeKind.CONTENT_CHANGED]

    lines: list[str] = [f"## {version}", ""]

    if added:
        lines.append("### Added")
        for change in added:
            rule = new.get(change.rule_id)
            lines.append(f"- {rule.id} ({rule.level.value}) -- {rule.name}")
        lines.append("")

    if level_changed or content_changed:
        lines.append("### Changed")
        for change in level_changed:
            rule = new.get(change.rule_id)
            old_level = change.old_level.value if change.old_level else "?"
            new_level = change.new_level.value if change.new_level else "?"
            lines.append(f"- {rule.id}: {old_level} -> {new_level} -- {rule.name}")
        for change in content_changed:
            rule = new.get(change.rule_id)
            lines.append(f"- {rule.id}: wording/examples updated -- {rule.name}")
        lines.append("")

    if removed:
        lines.append("### Removed")
        for change in removed:
            rule = old.get(change.rule_id)
            lines.append(f"- {rule.id} -- {rule.name}")
        lines.append("")

    if migration_notes:
        lines.append("#### Migration notes")
        lines.append("")
        lines.append(migration_notes)
        lines.append("")

    return "\n".join(lines)
```

- [ ] **Step 4: Run to verify it passes**

Run: `uv run pytest tests/release/test_changelog.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/arch_standard/release/changelog.py tests/release/test_changelog.py
git commit -m "$(cat <<'EOF'
feat: add release.changelog (per-version entry rendering)

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01GEq9yHV4hbB35DxtL11UFL
EOF
)"
```

### Task 18: `arch-standard changelog` — write the entry, require migration notes for `MUST` promotions

**Files:**
- Modify: `src/arch_standard/cli.py`
- Test: `tests/release/test_changelog_cli.py`

**Interfaces:**
- Consumes: `release.snapshot.{latest_snapshot_version, snapshot_dir}`, `release.diff.diff_catalogs`, `release.compatibility.find_unsanctioned_must_promotions` (reused only to know which changes are `MUST` promotions, not to gate on the sanction itself — that is `release-check`'s job), `release.changelog.render_changelog_entry`.
- Produces: `arch-standard changelog --version X.Y.Z [--rules-dir PATH] [--migration-notes PATH] [--changelog-file PATH]` — prepends the rendered entry above the existing `CHANGELOG.md` content (after its `# Changelog` header); errors if any change in the diff is a `LEVEL_CHANGED` promotion to `MUST`/`MUST*` and `--migration-notes` was not given.

- [ ] **Step 1: Write the failing test**

```python
# tests/release/test_changelog_cli.py
from __future__ import annotations

from pathlib import Path

import pytest

from arch_standard.cli import main

_RULE_TEMPLATE = """
rules:
  - id: ARCH-900
    name: example rule
    level: {level}
    automation: manual
    category: example
    description: an example rule for changelog testing
    rationale: exercises the changelog CLI end to end
    correct: |
      pass
    incorrect: |
      fail
    validation:
      tool: review
"""


def _write_rules(path: Path, level: str) -> None:
    path.mkdir(parents=True, exist_ok=True)
    (path / "example.yaml").write_text(_RULE_TEMPLATE.format(level=level), encoding="utf-8")


def test_given_must_promotion_without_migration_notes__when_changelog__then_fails(tmp_path: Path) -> None:
    rules_dir = tmp_path / "rules"
    _write_rules(rules_dir / ".released" / "1.1.0", level="SHOULD")
    _write_rules(rules_dir, level="MUST")
    changelog_file = tmp_path / "CHANGELOG.md"
    changelog_file.write_text("# Changelog\n\n", encoding="utf-8")

    exit_code = main(
        [
            "changelog",
            "--version",
            "2.0.0",
            "--rules-dir",
            str(rules_dir),
            "--changelog-file",
            str(changelog_file),
        ]
    )
    assert exit_code == 1


def test_given_must_promotion_with_migration_notes__when_changelog__then_prepends_entry(
    tmp_path: Path,
) -> None:
    rules_dir = tmp_path / "rules"
    _write_rules(rules_dir / ".released" / "1.1.0", level="SHOULD")
    _write_rules(rules_dir, level="MUST")
    changelog_file = tmp_path / "CHANGELOG.md"
    changelog_file.write_text("# Changelog\n\nolder entries here\n", encoding="utf-8")
    notes_file = tmp_path / "notes.md"
    notes_file.write_text("Upgrade guidance for ARCH-900.", encoding="utf-8")

    exit_code = main(
        [
            "changelog",
            "--version",
            "2.0.0",
            "--rules-dir",
            str(rules_dir),
            "--changelog-file",
            str(changelog_file),
            "--migration-notes",
            str(notes_file),
        ]
    )
    assert exit_code == 0
    content = changelog_file.read_text(encoding="utf-8")
    assert content.startswith("# Changelog\n\n## 2.0.0")
    assert "Upgrade guidance for ARCH-900." in content
    assert "older entries here" in content  # existing history preserved, not overwritten
```

- [ ] **Step 2: Run to verify it fails**

Run: `uv run pytest tests/release/test_changelog_cli.py -v`
Expected: FAIL — `changelog` is not a recognized subcommand yet.

- [ ] **Step 3: Implement**

```python
# src/arch_standard/cli.py — in _build_parser, after release_check
    changelog = sub.add_parser("changelog", help="render and prepend a CHANGELOG.md entry")
    changelog.add_argument("--version", required=True)
    changelog.add_argument("--rules-dir", default=None)
    changelog.add_argument("--changelog-file", default="CHANGELOG.md")
    changelog.add_argument("--migration-notes", default=None, help="path to a migration-notes file")
```

```python
# src/arch_standard/cli.py — new function
def _run_changelog(
    version: str, rules_dir_arg: str | None, changelog_file_arg: str, migration_notes_arg: str | None
) -> int:
    from arch_standard.release.changelog import render_changelog_entry
    from arch_standard.release.compatibility import find_unsanctioned_must_promotions
    from arch_standard.release.diff import ChangeKind, diff_catalogs
    from arch_standard.release.snapshot import latest_snapshot_version, snapshot_dir
    from arch_standard.rules.model import Level

    rules_dir = Path(rules_dir_arg) if rules_dir_arg else Path.cwd() / "rules"
    previous = latest_snapshot_version(rules_dir)
    if previous is None:
        print("no released snapshot to compare against -- run `arch-standard release-snapshot` first")
        return 1

    old_catalog = Catalog.load(snapshot_dir(rules_dir, previous))
    new_catalog = Catalog.load(rules_dir)
    changes = diff_catalogs(old_catalog, new_catalog)

    binding = (Level.MUST, Level.MUST_CONDITIONAL)
    must_promotions = [
        change
        for change in changes
        if change.kind == ChangeKind.LEVEL_CHANGED and change.new_level in binding
    ]
    # find_unsanctioned_must_promotions is release-check's own gate; changelog only
    # needs to know a MUST promotion happened at all, sanctioned or not, to require notes.
    del find_unsanctioned_must_promotions

    migration_notes: str | None = None
    if migration_notes_arg:
        migration_notes = Path(migration_notes_arg).read_text(encoding="utf-8").strip()
    elif must_promotions:
        promoted = ", ".join(change.rule_id for change in must_promotions)
        print(f"FAIL  {promoted} newly binding as MUST -- pass --migration-notes")
        return 1

    entry = render_changelog_entry(version, old_catalog, new_catalog, changes, migration_notes)

    changelog_path = Path(changelog_file_arg)
    existing = changelog_path.read_text(encoding="utf-8") if changelog_path.is_file() else "# Changelog\n\n"
    header, _, rest = existing.partition("\n\n")
    changelog_path.write_text(f"{header}\n\n{entry}\n{rest}", encoding="utf-8")
    print(f"wrote {changelog_path}")
    return 0
```

```python
# src/arch_standard/cli.py — main(), extend the whitelist and dispatch
    if argv[0] not in {
        "check", "docs", "release-snapshot", "release-check", "changelog", "-h", "--help",
    }:
        parser.print_usage()
        return 2
    args = parser.parse_args(argv)
    if args.command == "check":
        return _run_check(args.path, core=args.core)
    if args.command == "docs":
        return _run_docs(check=args.check)
    if args.command == "release-snapshot":
        return _run_release_snapshot(args.version)
    if args.command == "release-check":
        return _run_release_check(args.version, args.rules_dir)
    if args.command == "changelog":
        return _run_changelog(args.version, args.rules_dir, args.changelog_file, args.migration_notes)
    return 0
```

- [ ] **Step 4: Run to verify it passes**

Run: `uv run pytest tests/release/test_changelog_cli.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/arch_standard/cli.py tests/release/test_changelog_cli.py
git commit -m "$(cat <<'EOF'
feat: add arch-standard changelog (requires migration notes for new MUSTs)

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01GEq9yHV4hbB35DxtL11UFL
EOF
)"
```

### Task 19: seed the real `CHANGELOG.md`

**Files:**
- Create: `CHANGELOG.md`
- Modify: `tests/test_real_catalog.py`

**Interfaces:**
- Produces: a real `CHANGELOG.md` at the repo root documenting `0.1.0`, matching this repo's own actual history (the rule catalog, validator, and docgen shipped by the plans already merged to `master`). A regression test keeps it from silently disappearing, mirroring this repo's existing pattern of guarding generated/maintained docs (`test_real_catalog.py` already guards example paths and the `--core` count).

- [ ] **Step 1: Write the failing test**

```python
# append to tests/test_real_catalog.py
def test_given_repo_root__when_changelog_exists__then_starts_with_changelog_header() -> None:
    changelog = Path(__file__).resolve().parents[1] / "CHANGELOG.md"
    assert changelog.is_file(), "CHANGELOG.md is missing from the repo root"
    content = changelog.read_text(encoding="utf-8")
    assert content.startswith("# Changelog")
    assert "## 0.1.0" in content
```

- [ ] **Step 2: Run to verify it fails**

Run: `uv run pytest tests/test_real_catalog.py -k changelog -v`
Expected: FAIL — `CHANGELOG.md` does not exist yet.

- [ ] **Step 3: Implement**

```markdown
# Changelog

All notable changes to the Architecture Standard's rule catalog are recorded here,
one version per section. The compatibility policy (spec Section 16.3) governs
what kind of change requires which version bump; `arch-standard release-check`
enforces it, `arch-standard changelog` renders these entries.

## 0.1.0

Initial catalog and tooling: the rule catalog (`rules/*.yaml`), the `arch_standard`
validator package (import-linter contracts, the AST checker, structure and context-graph
checks), `ARCHITECTURE_STANDARD.md` generation, and CI. Includes the aggregate-module
level, the `<context>/read/` layer, the declared context dependency graph, and rule tiers
(12 core rules).
```

- [ ] **Step 4: Run to verify it passes**

Run: `uv run pytest tests/test_real_catalog.py -k changelog -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add CHANGELOG.md tests/test_real_catalog.py
git commit -m "$(cat <<'EOF'
docs: seed CHANGELOG.md with the 0.1.0 baseline

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01GEq9yHV4hbB35DxtL11UFL
EOF
)"
```

---

## Group E: the `copier` project template

**Worked example first.** Spec Sections 6.2 and 7.2 already walk through one concrete slice — `sales/orders`, `OrderService`, `Order.place`, `SqlAlchemyOrderRepository` — as the standard's own running example. Rather than invent a different example for the template, this group generates exactly that slice (with an in-memory repository, since a fresh project has no database configured yet), proving the whole pipeline — `arch-commons`, the version stamp, and the validator — works together end to end for a project that did not exist five minutes ago.

**Why no `entrypoints/http.py`, `cli.py`, `cron.py`, `events.py`, `read/`, or `shared/`:** the standard's own philosophy (spec Section 1, "Fixed shape, growing content") is explicit that a file does not exist until it has content — there is no "flat first, restructure later" step. A freshly generated project has exactly one aggregate, so `shared/` and `read/` have nothing to hold yet, and no transport is chosen yet, so no entrypoint file has real content. Scaffolding empty versions of any of these would itself be the anti-pattern Section 1 exists to prevent. The template ships only what has real content: the aggregate's full vertical slice, `bootstrap/` (the Composition Root), and `entrypoints/providers.py` (the one piece of entrypoint wiring every context needs regardless of transport).

### Task 20: `copier.yml` and the root skeleton files

**Files:**
- Create: `templates/copier.yml`
- Create: `templates/main.py.jinja`
- Create: `templates/pyproject.toml.jinja`
- Create: `templates/contexts.toml.jinja`
- Create: `templates/.arch-standard.jinja`
- Create: `templates/Makefile.jinja`
- Create: `templates/.github/workflows/ci.yml.jinja`
- Modify: `pyproject.toml` (root, add `copier` to dev deps)
- Create: `tests/templates/conftest.py`
- Create: `tests/templates/test_template_root_files.py`

**Interfaces:**
- Produces: the copier answers `project_name`, `project_slug`, `context_name` (default `"sales"`), `aggregate_name` (default `"order"`), `aggregate_module` (default `"{{ aggregate_name }}s"` → `"orders"`), `arch_standard_version`, `arch_commons_version`, `template_version`, `standard_git_url`. `tests/templates/conftest.py` exposes `TEMPLATE_ROOT` (path to `templates/`) for every task in this group.

- [ ] **Step 1: Write the failing test**

```python
# tests/templates/conftest.py
from __future__ import annotations

from pathlib import Path

TEMPLATE_ROOT = Path(__file__).resolve().parents[2] / "templates"
```

```python
# tests/templates/test_template_root_files.py
from __future__ import annotations

from pathlib import Path

import copier

from tests.templates.conftest import TEMPLATE_ROOT


def test_given_defaults__when_copied__then_root_files_render_with_no_leftover_jinja(
    tmp_path: Path,
) -> None:
    dest = tmp_path / "generated"
    copier.run_copy(str(TEMPLATE_ROOT), str(dest), defaults=True, overwrite=True, unsafe=True)

    for relative in ("main.py", "pyproject.toml", "contexts.toml", ".arch-standard", "Makefile"):
        content = (dest / relative).read_text(encoding="utf-8")
        assert "{{" not in content, f"{relative} has unrendered Jinja: {content!r}"

    assert (dest / ".github" / "workflows" / "ci.yml").is_file()
    assert 'name = "sales"' not in (dest / "pyproject.toml").read_text(encoding="utf-8")
    assert "[contexts.sales]" in (dest / "contexts.toml").read_text(encoding="utf-8")
    assert 'standard-version = "0.1.0"' in (dest / ".arch-standard").read_text(encoding="utf-8")
```

- [ ] **Step 2: Run to verify it fails**

Run: `uv run pytest tests/templates/test_template_root_files.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'copier'` (not a dev dependency yet), then, once added, `FileNotFoundError`/copier error since `templates/copier.yml` does not exist yet.

- [ ] **Step 3: Implement**

```toml
# pyproject.toml (root) — add copier to dev
[dependency-groups]
dev = ["pytest>=8", "ruff>=0.6", "mypy>=1.11", "types-pyyaml", "arch-commons", "copier>=9"]
```

```yaml
# templates/copier.yml
project_name:
  type: str
  help: "Human-readable project name"
  default: "My Project"

project_slug:
  type: str
  help: "Python distribution slug (kebab-case)"
  default: "{{ project_name.lower().replace(' ', '-') }}"

context_name:
  type: str
  help: "The first bounded context's folder name (snake_case)"
  default: "sales"

aggregate_name:
  type: str
  help: "The first aggregate's name, singular (snake_case)"
  default: "order"

aggregate_module:
  type: str
  help: "The aggregate module's folder name, usually the plural"
  default: "{{ aggregate_name }}s"

arch_standard_version:
  type: str
  help: "arch-standard version to pin as a dependency"
  default: "0.1.0"

arch_commons_version:
  type: str
  help: "arch-commons version to pin as a dependency"
  default: "0.1.0"

template_version:
  type: str
  help: "This template's own version, recorded in the .arch-standard stamp"
  default: "0.1.0"

standard_git_url:
  type: str
  help: >-
    Git URL of the architecture-standard repo. arch-standard and arch-commons are
    not published to a package index yet, so they are installed from here directly --
    replace with your actual remote before generating a real project.
  default: "https://github.com/CHANGE_ME/architecture-standard.git"

_tasks:
  - "arch-standard render-importlinter ."
```

```python
# templates/main.py.jinja
from __future__ import annotations

from bootstrap import build_container


def main() -> None:
    container = build_container()
    # Wire real entrypoints here (HTTP server, consumer loop, CLI) as they
    # gain content -- there is none yet, so none are scaffolded (spec Section 1).
    del container


if __name__ == "__main__":
    main()
```

```toml
# templates/pyproject.toml.jinja
[project]
name = "{{ project_slug }}"
version = "0.1.0"
description = "{{ project_name }}"
requires-python = ">=3.12"
dependencies = [
    "arch-standard @ git+{{ standard_git_url }}@v{{ arch_standard_version }}",
    "arch-commons @ git+{{ standard_git_url }}@v{{ arch_commons_version }}#subdirectory=packages/arch-commons",
]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["src/{{ context_name }}", "src/bootstrap"]

[dependency-groups]
dev = ["pytest>=8", "ruff>=0.6", "mypy>=1.11"]
```

```toml
# templates/contexts.toml.jinja
[contexts.{{ context_name }}]
depends_on = []
```

```toml
# templates/.arch-standard.jinja
standard-version = "{{ arch_standard_version }}"
template-version = "{{ template_version }}"
```

```makefile
# templates/Makefile.jinja
.PHONY: install lint test check
install:
	uv sync
lint:
	uv run ruff check . && uv run ruff format --check . && uv run mypy
test:
	uv run pytest
check:
	uv run arch-standard check .
```

```yaml
# templates/.github/workflows/ci.yml.jinja
name: ci
on:
  push: { branches: [main, master] }
  pull_request:
jobs:
  validate:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v3
      - run: uv sync
      - run: uv run ruff check .
      - run: uv run ruff format --check .
      - run: uv run mypy
      - run: uv run pytest
      - run: uv run arch-standard render-importlinter .
      - run: uv run arch-standard check .
```

- [ ] **Step 4: Run to verify it passes**

Run: `uv sync && uv run pytest tests/templates/test_template_root_files.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add pyproject.toml templates/copier.yml templates/main.py.jinja templates/pyproject.toml.jinja \
        templates/contexts.toml.jinja templates/.arch-standard.jinja templates/Makefile.jinja \
        templates/.github/workflows/ci.yml.jinja tests/templates/conftest.py \
        tests/templates/test_template_root_files.py uv.lock
git commit -m "$(cat <<'EOF'
feat: add the copier template's root skeleton files

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01GEq9yHV4hbB35DxtL11UFL
EOF
)"
```

### Task 21: `bootstrap/` and `entrypoints/providers.py` templates

**Files:**
- Create: `templates/bootstrap/__init__.py.jinja`
- Create: `templates/src/{{ context_name }}/entrypoints/providers.py.jinja`
- Create: `tests/templates/test_template_bootstrap_providers.py`

**Interfaces:**
- Consumes: `commons.infrastructure.{in_memory_unit_of_work.InMemoryUnitOfWork, in_memory_event_bus.InMemoryEventBus, system_clock.SystemClock}` (Task 7) — referenced by import path only in this task; actually exercised in Task 25.
- Produces: `bootstrap.build_container() -> Container` and `entrypoints.providers.<aggregate_name>_service() -> <ClassName>Service`, matching spec Section 7.2's provider pattern (a thin function pulling a wired service from the container).

- [ ] **Step 1: Write the failing test**

```python
# tests/templates/test_template_bootstrap_providers.py
from __future__ import annotations

from pathlib import Path

import copier

from tests.templates.conftest import TEMPLATE_ROOT


def test_given_defaults__when_copied__then_bootstrap_and_providers_reference_order_service(
    tmp_path: Path,
) -> None:
    dest = tmp_path / "generated"
    copier.run_copy(str(TEMPLATE_ROOT), str(dest), defaults=True, overwrite=True, unsafe=True)

    bootstrap = (dest / "bootstrap" / "__init__.py").read_text(encoding="utf-8")
    assert "from sales.orders.application.order_service import" in bootstrap
    assert "OrderService" in bootstrap
    assert "InMemoryUnitOfWork" in bootstrap and "SystemClock" in bootstrap

    providers = (dest / "src" / "sales" / "entrypoints" / "providers.py").read_text(encoding="utf-8")
    assert "def order_service() -> OrderService:" in providers
    assert "from bootstrap import build_container" in providers
```

- [ ] **Step 2: Run to verify it fails**

Run: `uv run pytest tests/templates/test_template_bootstrap_providers.py -v`
Expected: FAIL — `bootstrap/__init__.py` does not exist in the generated tree.

- [ ] **Step 3: Implement**

```python
# templates/bootstrap/__init__.py.jinja
from __future__ import annotations

from dataclasses import dataclass

from commons.infrastructure.in_memory_event_bus import InMemoryEventBus
from commons.infrastructure.in_memory_unit_of_work import InMemoryUnitOfWork
from commons.infrastructure.system_clock import SystemClock

from {{ context_name }}.{{ aggregate_module }}.application.{{ aggregate_name }}_service import (
    {{ aggregate_name | capitalize }}Service,
)
from {{ context_name }}.{{ aggregate_module }}.infrastructure.{{ aggregate_name }}_repository import (
    InMemory{{ aggregate_name | capitalize }}Repository,
)


@dataclass(frozen=True)
class Container:
    {{ aggregate_name }}_service: {{ aggregate_name | capitalize }}Service


def build_container() -> Container:
    """Composition Root: construct singletons and wire services (ARCH-017 --
    nothing outside this module imports it)."""
    uow = InMemoryUnitOfWork()
    repository = InMemory{{ aggregate_name | capitalize }}Repository()
    service = {{ aggregate_name | capitalize }}Service(
        uow=uow, repository=repository, clock=SystemClock(), bus=InMemoryEventBus()
    )
    return Container({{ aggregate_name }}_service=service)
```

```python
# templates/src/{{ context_name }}/entrypoints/providers.py.jinja
from __future__ import annotations

from bootstrap import build_container

from {{ context_name }}.{{ aggregate_module }}.application.{{ aggregate_name }}_service import (
    {{ aggregate_name | capitalize }}Service,
)

_container = build_container()


def {{ aggregate_name }}_service() -> {{ aggregate_name | capitalize }}Service:
    return _container.{{ aggregate_name }}_service
```

- [ ] **Step 4: Run to verify it passes**

Run: `uv run pytest tests/templates/test_template_bootstrap_providers.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add templates/bootstrap/__init__.py.jinja "templates/src/{{ context_name }}/entrypoints/providers.py.jinja" \
        tests/templates/test_template_bootstrap_providers.py
git commit -m "$(cat <<'EOF'
feat: add the template's bootstrap/ Composition Root and entrypoints/providers.py

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01GEq9yHV4hbB35DxtL11UFL
EOF
)"
```

### Task 22: the example aggregate's domain layer

**Files:**
- Create: `templates/src/{{ context_name }}/{{ aggregate_module }}/domain/model/{{ aggregate_name }}.py.jinja`
- Create: `templates/src/{{ context_name }}/{{ aggregate_module }}/domain/model/exceptions.py.jinja`
- Create: `templates/src/{{ context_name }}/{{ aggregate_module }}/domain/model/events.py.jinja`
- Create: `templates/src/{{ context_name }}/{{ aggregate_module }}/domain/model/ports.py.jinja`
- Create: `tests/templates/test_template_domain_layer.py`

**Interfaces:**
- Consumes: `commons.types.identity.EntityId` (Task 3), `commons.types.errors.DomainError` (Task 2).
- Produces: `{{ClassName}}Id(EntityId)`, `{{ClassName}}(id, name, pending_events)` with a `create(id, name, occurred_at)` classmethod and `clear_pending_events()` (the drain convention Task 7's `InMemoryUnitOfWork` relies on), `{{ClassName}}Created(id, occurred_at)` (ARCH-023: frozen, past tense), `{{ClassName}}NotFound(DomainError)`, `{{ClassName}}Repository` Protocol.

- [ ] **Step 1: Write the failing test**

```python
# tests/templates/test_template_domain_layer.py
from __future__ import annotations

import py_compile
from pathlib import Path

import copier

from tests.templates.conftest import TEMPLATE_ROOT

_DOMAIN_MODEL = "src/sales/orders/domain/model"


def test_given_defaults__when_copied__then_domain_layer_files_compile_and_have_expected_names(
    tmp_path: Path,
) -> None:
    dest = tmp_path / "generated"
    copier.run_copy(str(TEMPLATE_ROOT), str(dest), defaults=True, overwrite=True, unsafe=True)

    for filename in ("order.py", "exceptions.py", "events.py", "ports.py"):
        path = dest / _DOMAIN_MODEL / filename
        py_compile.compile(str(path), doraise=True)

    order_py = (dest / _DOMAIN_MODEL / "order.py").read_text(encoding="utf-8")
    assert "class OrderId(EntityId):" in order_py
    assert "class Order:" in order_py
    assert "def create(" in order_py

    exceptions_py = (dest / _DOMAIN_MODEL / "exceptions.py").read_text(encoding="utf-8")
    assert "class OrderNotFound(DomainError):" in exceptions_py

    events_py = (dest / _DOMAIN_MODEL / "events.py").read_text(encoding="utf-8")
    assert "class OrderCreated:" in events_py

    ports_py = (dest / _DOMAIN_MODEL / "ports.py").read_text(encoding="utf-8")
    assert "class OrderRepository(Protocol):" in ports_py
```

- [ ] **Step 2: Run to verify it fails**

Run: `uv run pytest tests/templates/test_template_domain_layer.py -v`
Expected: FAIL — the domain-model files do not exist in the generated tree.

- [ ] **Step 3: Implement**

```python
# templates/src/{{ context_name }}/{{ aggregate_module }}/domain/model/{{ aggregate_name }}.py.jinja
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from commons.types.identity import EntityId

from {{ context_name }}.{{ aggregate_module }}.domain.model.events import (
    {{ aggregate_name | capitalize }}Created,
)


@dataclass(frozen=True)
class {{ aggregate_name | capitalize }}Id(EntityId):
    pass


@dataclass
class {{ aggregate_name | capitalize }}:
    """Aggregate root -- one module, one aggregate (spec Section 2.2)."""

    id: {{ aggregate_name | capitalize }}Id
    name: str
    pending_events: list[object] = field(default_factory=list, compare=False)

    @classmethod
    def create(
        cls, id: {{ aggregate_name | capitalize }}Id, name: str, occurred_at: datetime
    ) -> "{{ aggregate_name | capitalize }}":
        {{ aggregate_name }} = cls(id=id, name=name)
        {{ aggregate_name }}.pending_events.append(
            {{ aggregate_name | capitalize }}Created(id=id, occurred_at=occurred_at)
        )
        return {{ aggregate_name }}

    def clear_pending_events(self) -> None:
        self.pending_events.clear()
```

```python
# templates/src/{{ context_name }}/{{ aggregate_module }}/domain/model/exceptions.py.jinja
from __future__ import annotations

from commons.types.errors import DomainError

from {{ context_name }}.{{ aggregate_module }}.domain.model.{{ aggregate_name }} import (
    {{ aggregate_name | capitalize }}Id,
)


class {{ aggregate_name | capitalize }}NotFound(DomainError):
    def __init__(self, {{ aggregate_name }}_id: {{ aggregate_name | capitalize }}Id) -> None:
        super().__init__("{{ aggregate_name | capitalize }} not found: " + str({{ aggregate_name }}_id))
```

```python
# templates/src/{{ context_name }}/{{ aggregate_module }}/domain/model/events.py.jinja
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class {{ aggregate_name | capitalize }}Created:
    """Past-tense, immutable domain event (ARCH-023)."""

    id: object
    occurred_at: datetime
```

```python
# templates/src/{{ context_name }}/{{ aggregate_module }}/domain/model/ports.py.jinja
from __future__ import annotations

from typing import Protocol

from {{ context_name }}.{{ aggregate_module }}.domain.model.{{ aggregate_name }} import (
    {{ aggregate_name | capitalize }},
    {{ aggregate_name | capitalize }}Id,
)


class {{ aggregate_name | capitalize }}Repository(Protocol):
    def next_identity(self) -> str: ...
    def add(self, {{ aggregate_name }}: {{ aggregate_name | capitalize }}) -> None: ...
    def get(self, {{ aggregate_name }}_id: {{ aggregate_name | capitalize }}Id) -> {{ aggregate_name | capitalize }}: ...
```

- [ ] **Step 4: Run to verify it passes**

Run: `uv run pytest tests/templates/test_template_domain_layer.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add "templates/src/{{ context_name }}/{{ aggregate_module }}/domain" \
        tests/templates/test_template_domain_layer.py
git commit -m "$(cat <<'EOF'
feat: add the template's example aggregate domain layer

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01GEq9yHV4hbB35DxtL11UFL
EOF
)"
```

### Task 23: the example aggregate's application and infrastructure layers

**Files:**
- Create: `templates/src/{{ context_name }}/{{ aggregate_module }}/application/{{ aggregate_name }}_service.py.jinja`
- Create: `templates/src/{{ context_name }}/{{ aggregate_module }}/infrastructure/{{ aggregate_name }}_repository.py.jinja`
- Create: `tests/templates/test_template_application_infrastructure.py`

**Interfaces:**
- Consumes: `commons.types.{clock.Clock, event_bus.EventBus, unit_of_work.UnitOfWork}` (Tasks 4–6), `commons.infrastructure.uuid7_id_generator.Uuid7IdGenerator` (Task 7), the domain layer from Task 22.
- Produces: `Create{{ClassName}}(name)` command, `{{ClassName}}Service(uow, repository, clock, bus).create_{{aggregate_name}}(command) -> {{ClassName}}Id` (spec Section 6.2's shape, one method per use case), `InMemory{{ClassName}}Repository` implementing `{{ClassName}}Repository`.

- [ ] **Step 1: Write the failing test**

```python
# tests/templates/test_template_application_infrastructure.py
from __future__ import annotations

import py_compile
from pathlib import Path

import copier

from tests.templates.conftest import TEMPLATE_ROOT


def test_given_defaults__when_copied__then_application_and_infrastructure_files_compile(
    tmp_path: Path,
) -> None:
    dest = tmp_path / "generated"
    copier.run_copy(str(TEMPLATE_ROOT), str(dest), defaults=True, overwrite=True, unsafe=True)

    service_path = dest / "src/sales/orders/application/order_service.py"
    repository_path = dest / "src/sales/orders/infrastructure/order_repository.py"
    py_compile.compile(str(service_path), doraise=True)
    py_compile.compile(str(repository_path), doraise=True)

    service_py = service_path.read_text(encoding="utf-8")
    assert "class CreateOrder:" in service_py
    assert "class OrderService:" in service_py
    assert "def create_order(self, command: CreateOrder) -> OrderId:" in service_py

    repository_py = repository_path.read_text(encoding="utf-8")
    assert "class InMemoryOrderRepository:" in repository_py
    assert "Uuid7IdGenerator" in repository_py
```

- [ ] **Step 2: Run to verify it fails**

Run: `uv run pytest tests/templates/test_template_application_infrastructure.py -v`
Expected: FAIL — the application/infrastructure files do not exist in the generated tree.

- [ ] **Step 3: Implement**

```python
# templates/src/{{ context_name }}/{{ aggregate_module }}/application/{{ aggregate_name }}_service.py.jinja
from __future__ import annotations

from dataclasses import dataclass

from commons.types.clock import Clock
from commons.types.event_bus import EventBus
from commons.types.unit_of_work import UnitOfWork

from {{ context_name }}.{{ aggregate_module }}.domain.model.{{ aggregate_name }} import (
    {{ aggregate_name | capitalize }},
    {{ aggregate_name | capitalize }}Id,
)
from {{ context_name }}.{{ aggregate_module }}.domain.model.ports import (
    {{ aggregate_name | capitalize }}Repository,
)


@dataclass(frozen=True)
class Create{{ aggregate_name | capitalize }}:
    name: str


class {{ aggregate_name | capitalize }}Service:
    def __init__(
        self,
        uow: UnitOfWork,
        repository: {{ aggregate_name | capitalize }}Repository,
        clock: Clock,
        bus: EventBus,
    ) -> None:
        self._uow = uow
        self._repository = repository
        self._clock = clock
        self._bus = bus

    def create_{{ aggregate_name }}(
        self, command: Create{{ aggregate_name | capitalize }}
    ) -> {{ aggregate_name | capitalize }}Id:
        with self._uow:
            {{ aggregate_name }}_id = {{ aggregate_name | capitalize }}Id(
                value=self._repository.next_identity()
            )
            {{ aggregate_name }} = {{ aggregate_name | capitalize }}.create(
                id={{ aggregate_name }}_id, name=command.name, occurred_at=self._clock.now()
            )
            self._repository.add({{ aggregate_name }})
            self._uow.track({{ aggregate_name }})
            self._uow.commit()
        self._bus.publish_all(self._uow.collect_new_events())
        return {{ aggregate_name }}_id
```

```python
# templates/src/{{ context_name }}/{{ aggregate_module }}/infrastructure/{{ aggregate_name }}_repository.py.jinja
from __future__ import annotations

from commons.infrastructure.uuid7_id_generator import Uuid7IdGenerator

from {{ context_name }}.{{ aggregate_module }}.domain.model.{{ aggregate_name }} import (
    {{ aggregate_name | capitalize }},
    {{ aggregate_name | capitalize }}Id,
)
from {{ context_name }}.{{ aggregate_module }}.domain.model.exceptions import (
    {{ aggregate_name | capitalize }}NotFound,
)


class InMemory{{ aggregate_name | capitalize }}Repository:
    """Dict-backed repository for projects with no real store configured yet
    (ARCH-039: a real adapter must honor this same contract)."""

    def __init__(self) -> None:
        self._by_id: dict[str, {{ aggregate_name | capitalize }}] = {}
        self._id_generator = Uuid7IdGenerator()

    def next_identity(self) -> str:
        return self._id_generator.new_id()

    def add(self, {{ aggregate_name }}: {{ aggregate_name | capitalize }}) -> None:
        self._by_id[{{ aggregate_name }}.id.value] = {{ aggregate_name }}

    def get(
        self, {{ aggregate_name }}_id: {{ aggregate_name | capitalize }}Id
    ) -> {{ aggregate_name | capitalize }}:
        found = self._by_id.get({{ aggregate_name }}_id.value)
        if found is None:
            raise {{ aggregate_name | capitalize }}NotFound({{ aggregate_name }}_id)
        return found
```

- [ ] **Step 4: Run to verify it passes**

Run: `uv run pytest tests/templates/test_template_application_infrastructure.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add "templates/src/{{ context_name }}/{{ aggregate_module }}/application" \
        "templates/src/{{ context_name }}/{{ aggregate_module }}/infrastructure" \
        tests/templates/test_template_application_infrastructure.py
git commit -m "$(cat <<'EOF'
feat: add the template's example aggregate application and infrastructure layers

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01GEq9yHV4hbB35DxtL11UFL
EOF
)"
```

### Task 24: `arch-standard render-importlinter` — a static `.importlinter` for generated (and any) projects

**Files:**
- Modify: `src/arch_standard/cli.py`
- Create: `tests/templates/test_render_importlinter.py`

**Interfaces:**
- Consumes: `arch_standard.checks.import_contracts.build_contracts`, `arch_standard.checks.base.ProjectLayout` (existing).
- Produces: `arch-standard render-importlinter [path]` — writes `<path>/.importlinter` from the project's current structure. `arch-standard check` already computes this contract set in memory on every run (Task 10's fix included); this command exposes the same computation as a static file for tools that invoke `lint-imports` directly (pre-commit, an editor plugin) without going through `arch-standard check`. This is also what `copier.yml`'s `_tasks` entry (Task 20) invokes after generation.

- [ ] **Step 1: Write the failing test**

```python
# tests/templates/test_render_importlinter.py
from __future__ import annotations

from pathlib import Path

from arch_standard.cli import main


def test_given_a_plain_project__when_render_importlinter__then_writes_a_dot_importlinter(
    tmp_path: Path,
) -> None:
    for rel in [
        "src/sales/orders/domain/model/order.py",
        "src/sales/orders/application/order_service.py",
    ]:
        f = tmp_path / rel
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text("", encoding="utf-8")

    exit_code = main(["render-importlinter", str(tmp_path)])
    assert exit_code == 0

    ini = (tmp_path / ".importlinter").read_text(encoding="utf-8")
    assert "[importlinter]" in ini
    assert "ARCH-layers-sales-orders" in ini
```

- [ ] **Step 2: Run to verify it fails**

Run: `uv run pytest tests/templates/test_render_importlinter.py -v`
Expected: FAIL — `render-importlinter` is not a recognized subcommand.

- [ ] **Step 3: Implement**

```python
# src/arch_standard/cli.py — add import
from arch_standard.checks.import_contracts import build_contracts
```

```python
# src/arch_standard/cli.py — in _build_parser, after changelog
    render_importlinter = sub.add_parser(
        "render-importlinter", help="write a static .importlinter from the current project structure"
    )
    render_importlinter.add_argument("path", nargs="?", default=".", help="project root (default: cwd)")
```

```python
# src/arch_standard/cli.py — new function
def _run_render_importlinter(path: str) -> int:
    root = Path(path).resolve()
    layout = ProjectLayout.detect(root)
    ini = build_contracts(layout)
    (root / ".importlinter").write_text(ini, encoding="utf-8")
    print(f"wrote {root / '.importlinter'}")
    return 0
```

```python
# src/arch_standard/cli.py — main(), extend the whitelist and dispatch
    if argv[0] not in {
        "check", "docs", "release-snapshot", "release-check", "changelog",
        "render-importlinter", "-h", "--help",
    }:
        parser.print_usage()
        return 2
    args = parser.parse_args(argv)
    if args.command == "check":
        return _run_check(args.path, core=args.core)
    if args.command == "docs":
        return _run_docs(check=args.check)
    if args.command == "release-snapshot":
        return _run_release_snapshot(args.version)
    if args.command == "release-check":
        return _run_release_check(args.version, args.rules_dir)
    if args.command == "changelog":
        return _run_changelog(args.version, args.rules_dir, args.changelog_file, args.migration_notes)
    if args.command == "render-importlinter":
        return _run_render_importlinter(args.path)
    return 0
```

- [ ] **Step 4: Run to verify it passes**

Run: `uv run pytest tests/templates/test_render_importlinter.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/arch_standard/cli.py tests/templates/test_render_importlinter.py
git commit -m "$(cat <<'EOF'
feat: add arch-standard render-importlinter (static .importlinter output)

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01GEq9yHV4hbB35DxtL11UFL
EOF
)"
```

### Task 25: end-to-end proof — a generated project runs its use case and passes `arch-standard check --core`

**Files:**
- Create: `tests/templates/test_generated_project_end_to_end.py`

**Interfaces:**
- Consumes: everything from Tasks 1–24. No new production code — this task is the plan's own acceptance test.

- [ ] **Step 1: Write the failing test**

```python
# tests/templates/test_generated_project_end_to_end.py
from __future__ import annotations

import sys
from pathlib import Path

import copier
import pytest

from arch_standard.cli import main
from tests.templates.conftest import TEMPLATE_ROOT

_COMMONS_SRC = Path(__file__).resolve().parents[2] / "packages" / "arch-commons" / "src"

_GENERATED_MODULE_PREFIXES = ("bootstrap", "sales", "commons")


def _reset_generated_modules() -> None:
    for name in list(sys.modules):
        if name.startswith(_GENERATED_MODULE_PREFIXES):
            del sys.modules[name]


@pytest.fixture(autouse=True)
def _clean_module_cache() -> None:
    _reset_generated_modules()
    yield
    _reset_generated_modules()


def test_given_a_freshly_generated_project__when_service_runs__then_order_is_created_and_event_published(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    dest = tmp_path / "generated"
    copier.run_copy(str(TEMPLATE_ROOT), str(dest), defaults=True, overwrite=True, unsafe=True)

    monkeypatch.syspath_prepend(str(dest / "src"))
    monkeypatch.syspath_prepend(str(dest))  # bootstrap/ lives at the project root
    monkeypatch.syspath_prepend(str(_COMMONS_SRC))

    import importlib

    bootstrap = importlib.import_module("bootstrap")
    container = bootstrap.build_container()

    order_service_module = importlib.import_module("sales.orders.application.order_service")
    order_id = container.order_service.create_order(order_service_module.CreateOrder(name="widget"))

    assert order_id.value

    bus = container.order_service._bus  # type: ignore[attr-defined]
    assert len(bus.published) == 1


def test_given_a_freshly_generated_project__when_render_importlinter_and_check__then_core_rules_pass(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    dest = tmp_path / "generated"
    copier.run_copy(str(TEMPLATE_ROOT), str(dest), defaults=True, overwrite=True, unsafe=True)

    # Simulates copier.yml's `_tasks` entry (a real `arch-standard render-importlinter .`
    # subprocess at generation time) in-process, so this test does not depend on PATH
    # resolution inside the test's own subprocess environment.
    render_exit_code = main(["render-importlinter", str(dest)])
    assert render_exit_code == 0

    check_exit_code = main(["check", str(dest), "--core"])
    output = capsys.readouterr().out

    assert check_exit_code == 0, output
    assert "FAIL" not in output
```

- [ ] **Step 2: Run to verify it fails**

Run: `uv run pytest tests/templates/test_generated_project_end_to_end.py -v`
Expected: FAIL before Tasks 20–24 exist (this test is written last, against the already-implemented template, so in normal execution order it should already be close to passing — run it first to confirm the exact failure mode matches what's expected, e.g. an import error or a specific `FAIL` line, not a silent false positive).

- [ ] **Step 3: Fix whatever the failure reveals**

This task is deliberately a verification step, not a new-feature step: if Step 2 fails, the failure is almost always one of two things carried over from Tasks 20–24 —

- A wrong import path or class name in one of the `.jinja` templates (fix the template file directly; there is no separate "implementation" here since Tasks 20–24 already wrote the templates).
- `render-importlinter`'s output not matching what `ImportContractsCheck` expects at `check` time (re-read Task 10 and Task 24 — both call the same `build_contracts`, so a mismatch means one of the two call sites diverged; make them call it identically).

Run `uv run arch-standard check <path-printed-by-a-failing-test-run> --core` directly against a `copier copy`'d tmp directory to see the real `ARCH-xxx FAIL` lines if the second test fails, and fix the specific rule's violation in the relevant template file.

- [ ] **Step 4: Run to verify it passes**

Run: `uv run pytest tests/templates/test_generated_project_end_to_end.py -v`
Expected: PASS — both tests green: the generated project's own use case runs and publishes an event, and `arch-standard check --core` on the generated tree reports zero `FAIL`s.

- [ ] **Step 5: Commit**

```bash
git add tests/templates/test_generated_project_end_to_end.py
git commit -m "$(cat <<'EOF'
test: prove a freshly generated project runs its use case and passes
arch-standard check --core end to end

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01GEq9yHV4hbB35DxtL11UFL
EOF
)"
```

---

## Self-Review

**1. Spec coverage.** Section 8.1 (`arch-commons` separately versioned, `commons.types`/`commons.infrastructure`, governance, ARCH-015/016/034/035) → Tasks 1–10. Section 7.2 (`UnitOfWork` Protocol verbatim, SQLAlchemy reference impl, `InMemoryUnitOfWork`) → Tasks 6, 7, 8. Section 7.3 (outbox, "machinery lives in `commons/infrastructure/outbox.py`") → Task 9. Section 5.1/ARCH-004 (`domain`/`application` never call `datetime.now()` directly) → enforced by threading `Clock`/`occurred_at` through Tasks 4, 7, 22, 23 rather than calling it inline. Section 0 "Identifier generation... UUIDv7" → Task 7's `Uuid7IdGenerator`, used by Task 23. Section 16.3 version stamp shape and drift notice → Tasks 11–12. Section 16.3 compatibility table and "a new MUST never lands directly" → Tasks 13–16 (the concrete SHOULD→MUST worked example is exercised both at the unit level in Task 15 and end-to-end via the CLI in Task 16). Section 16.3 CHANGELOG requirement, "for a major, the migration notes for each newly-binding MUST" → Tasks 17–19. Section 16.3 "the project template... `copier`... `src/` skeleton + `.importlinter` + CI + `check` command" → Tasks 20–25 (`.importlinter` specifically via Task 24's `render-importlinter`, reusing Task 10's corrected `build_contracts`). Section 1 "fixed shape, growing content" → explicitly the reason Group E's intro gives for omitting empty entrypoint/read/shared scaffolding. Trade-off log row B (`IdGenerator` in `commons/types/`) → Task 5. Row E (minimal base classes + conventions) → Task 7's duck-typed `pending_events`/`clear_pending_events()` convention, called out explicitly rather than assumed. Section 17 row C (multi-repo/service-per-context topology deferred to v2) → this plan's own "second package in this repo, not a second repo" decision is consistent with that deferral, stated in the Architecture summary.

**2. Placeholder scan.** No task contains "TBD", "add appropriate error handling", or an unshown test. Task 25 (the acceptance test) is the one task without a from-scratch "implementation" step by design — it is scoped explicitly as a verification-and-fix step against code Tasks 20–24 already wrote, with concrete instructions for what to check if it fails, not a deferred placeholder.

**3. Type consistency.** `EntityId(value: str)` (Task 3) is the base for every `{{ClassName}}Id` in Task 22, consistently constructed as `{{ClassName}}Id(value=...)` in Task 23. `DomainEvent` (Task 4, structural, `occurred_at: datetime`) is the type `UnitOfWork.collect_new_events` (Task 6) returns, and is what `InMemoryUnitOfWork`/`SqlAlchemyUnitOfWork` (Tasks 7–8) drain via the same `pending_events`/`clear_pending_events()` duck-typed convention, which Task 22's generated `{{ClassName}}` aggregate also implements — verified directly by Task 25's live import-and-run test, not just by template text matching. `Clock.now() -> datetime`, `EventBus.publish_all(events: Iterable[DomainEvent]) -> None`, `IdGenerator.new_id() -> str` (Tasks 4–5) are each implemented exactly once concretely (`SystemClock`, `InMemoryEventBus`, `Uuid7IdGenerator`, Task 7) and consumed with matching signatures in Task 23's `{{ClassName}}Service` and Task 23's `InMemory{{ClassName}}Repository`. `RuleChange(rule_id, kind, old_level, new_level)` and `ChangeKind` (Task 14) are consumed identically by `release.compatibility` (Task 15), the `release-check` CLI (Task 16), and `release.changelog` (Task 17). `write_snapshot`/`list_snapshot_versions`/`latest_snapshot_version`/`snapshot_dir` (Task 13) are used with the same signatures in Tasks 16 and 18. `build_contracts(project: ProjectLayout) -> str` (existing, corrected in Task 10) is called identically by `_run_check` (existing) and `_run_render_importlinter` (Task 24) — the exact invariant Task 25's second test exists to verify.

---

Plan complete and saved to `docs/superpowers/plans/2026-09-06-distribution-and-release-engineering.md`.
