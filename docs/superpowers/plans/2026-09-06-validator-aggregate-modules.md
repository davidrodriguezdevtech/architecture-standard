# Validator: Aggregate Modules, Read Layer, Context Graph — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Teach the `arch_standard` validator the restructured standard — the aggregate-module level, the `<context>/read/` layer, the declared context dependency graph, rule tiers, and rules ARCH-046..053.

**Architecture:** `ProjectLayout` gains a second structural level (context → aggregate module) plus `shared_dir` and `read_dir`. The four existing checks are migrated to walk it; two new checks are added (`StructureCheck` for filesystem-shaped rules, `ContextGraphCheck` for `contexts.toml`). The rule catalog gains a `tier` field and eight new rules. Migration is additive-then-cutover: new layout support lands first and the old accessors are removed only in Task 10, so the suite stays green throughout.

**Tech Stack:** Python 3.12+, `uv`, `pytest`, `pydantic` v2, `PyYAML`, `tomllib` (stdlib), `import-linter` + `grimp`, `ruff`, `mypy --strict`.

**Spec:** `docs/superpowers/specs/2026-09-05-architecture-standard-v1-design.md` — read Sections 2 (structure, the two levels, what-goes-where, read layer), 3.6/3.7 (cross-aggregate flow, context graph), 5.5 (projections vs read), 8.1 (`arch-commons`), 9 (rule catalog + tiers), 15 (thresholds).

**Not in this plan (Plan 3):** extracting `arch-commons` into a published package, the `.arch-standard` version stamp and drift notice, the CHANGELOG/compatibility tooling, and the `copier` template. Those are release engineering and depend on this plan closing the catalog.

## Global Constraints

- Python 3.12+. `from __future__ import annotations` at the top of every module.
- Passes `uv run ruff check .`, `uv run ruff format --check .`, `uv run mypy` (strict), `uv run pytest`, `uv run arch-standard docs --check`.
- Rule IDs `ARCH-NNN`. Levels `MUST | SHOULD | MAY | MUST*`. Automation `full | partial | manual`. **New:** tier `core | full`.
- **The 12 core rules are exactly:** ARCH-001, 002, 003, 005, 006, 008, 012, 021, 023, 031, 046, 051. Everything else is `tier: full`.
- CLI exit contract unchanged: exit `1` iff some `MUST`/`MUST*` rule has an unwaived `FAIL`.
- **Never change a rule's `level` in `rules/*.yaml` to make a test pass.** Change the test.
- Tests land in the same commit as the code. Conventional Commits. Every commit message ends with:
  ```
  Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
  Claude-Session: https://claude.ai/code/session_01DhkqTTF5yVxRVSH8jxNfcf
  ```
- Run `uv run ruff format .` before committing.
- `tests/fixtures/` is excluded from ruff and mypy and from pytest collection (`norecursedirs`). Fixture trees must still be importable Python with `__init__.py` at every level — `ImportContractsCheck` really imports them.

---

## File Structure

```text
src/arch_standard/
├── rules/
│   ├── model.py            # MODIFY: add Tier enum + Rule.tier
│   └── catalog.py          # MODIFY: add .core() filter
├── checks/
│   ├── base.py             # MODIFY: ProjectLayout gains modules()/shared_dir()/read_dir()
│   ├── import_contracts.py # MODIFY: per-module layers, ARCH-046, ARCH-052
│   ├── ast_rules.py        # MODIFY: walk aggregate modules; ARCH-049
│   ├── banned_symbols.py   # MODIFY: walk modules + shared/; ARCH-053
│   ├── schemas.py          # MODIFY: paths only
│   ├── structure.py        # CREATE: ARCH-047, ARCH-048, ARCH-051
│   ├── context_graph.py    # CREATE: ARCH-050 (contexts.toml)
│   └── __init__.py         # MODIFY: register the two new checks
├── report.py               # MODIFY: tier filtering
└── cli.py                  # MODIFY: --core flag
rules/                      # MODIFY: tier field on all; add ARCH-046..053; MUST* on 024/043/044
docs/standard/              # MODIFY: 02, 03, 05, 06, 08, 15 partials
tests/fixtures/
├── modular_project/        # CREATE (Task 2): the new canonical shape
├── good_project/           # MIGRATE (Task 10)
├── bad_project/            # MIGRATE (Task 10)
└── minimal_project/        # MIGRATE (Task 10)
```

---

## Task 1: `ProjectLayout` learns the aggregate-module level

**Files:**
- Modify: `src/arch_standard/checks/base.py`
- Test: `tests/checks/test_base.py`

**Interfaces:**
- Consumes: existing `ProjectLayout(root, src, contexts)`.
- Produces (added; existing `domain_dir(context)` / `application_dir(context)` / `infrastructure_dir(context)` stay until Task 10):
  - `_CONTEXT_RESERVED: frozenset[str]` = `{"entrypoints", "shared", "read"}`
  - `ProjectLayout.modules(context: str) -> tuple[str, ...]` — sorted dir names directly under `<src>/<context>` that are not in `_CONTEXT_RESERVED`, are not dot/underscore-prefixed, and contain at least one of `domain`/`application`/`infrastructure`.
  - `ProjectLayout.module_domain_dir(context: str, module: str) -> Path`
  - `ProjectLayout.module_application_dir(context: str, module: str) -> Path`
  - `ProjectLayout.module_infrastructure_dir(context: str, module: str) -> Path`
  - `ProjectLayout.shared_dir(context: str) -> Path` → `<src>/<context>/shared`
  - `ProjectLayout.read_dir(context: str) -> Path` → `<src>/<context>/read`
  - `ProjectLayout.iter_modules() -> Iterator[tuple[str, str]]` — yields `(context, module)` for every module in every context, contexts then modules in sorted order.
  - `detect()` changes: a directory under `src/` is a context if it contains `entrypoints/` **or** at least one aggregate module (a subdir holding a layer dir). The current rule (contains a layer dir directly) is kept as a third alternative so existing fixtures still detect until Task 10.

- [ ] **Step 1: Write the failing test**

```python
# append to tests/checks/test_base.py
from arch_standard.checks.base import ProjectLayout


def _make_modular(tmp_path: Path) -> Path:
    root = tmp_path / "proj"
    for rel in [
        "src/sales/entrypoints/http.py",
        "src/sales/shared/ids.py",
        "src/sales/read/customer_overview.py",
        "src/sales/users/domain/model/user.py",
        "src/sales/users/application/user_service.py",
        "src/sales/users/infrastructure/user_repository.py",
        "src/sales/orders/domain/model/order.py",
        "src/sales/orders/application/order_service.py",
    ]:
        f = root / rel
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text("", encoding="utf-8")
    return root


def test_given_modular_tree__when_detect__then_context_found(tmp_path: Path) -> None:
    layout = ProjectLayout.detect(_make_modular(tmp_path))
    assert layout.contexts == ("sales",)


def test_given_modular_tree__when_modules__then_reserved_dirs_excluded(tmp_path: Path) -> None:
    layout = ProjectLayout.detect(_make_modular(tmp_path))
    assert layout.modules("sales") == ("orders", "users")


def test_given_modular_tree__when_module_dirs__then_paths_are_nested(tmp_path: Path) -> None:
    root = _make_modular(tmp_path)
    layout = ProjectLayout.detect(root)
    assert layout.module_domain_dir("sales", "users") == root / "src/sales/users/domain"
    assert layout.module_application_dir("sales", "users") == root / "src/sales/users/application"
    assert layout.module_infrastructure_dir("sales", "users") == root / "src/sales/users/infrastructure"
    assert layout.shared_dir("sales") == root / "src/sales/shared"
    assert layout.read_dir("sales") == root / "src/sales/read"


def test_given_modular_tree__when_iter_modules__then_sorted_pairs(tmp_path: Path) -> None:
    layout = ProjectLayout.detect(_make_modular(tmp_path))
    assert list(layout.iter_modules()) == [("sales", "orders"), ("sales", "users")]


def test_given_dir_without_layers__when_modules__then_not_a_module(tmp_path: Path) -> None:
    root = _make_modular(tmp_path)
    (root / "src/sales/notes").mkdir()
    (root / "src/sales/notes/readme.py").write_text("", encoding="utf-8")
    layout = ProjectLayout.detect(root)
    assert "notes" not in layout.modules("sales")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/checks/test_base.py -k modular -v`
Expected: FAIL — `AttributeError: 'ProjectLayout' object has no attribute 'modules'`

- [ ] **Step 3: Implement**

```python
# src/arch_standard/checks/base.py — add near the existing constants
_CONTEXT_RESERVED = frozenset({"entrypoints", "shared", "read"})
_LAYER_DIRS = ("domain", "application", "infrastructure")


def _has_layer(path: Path) -> bool:
    return any((path / layer).is_dir() for layer in _LAYER_DIRS)
```

```python
# inside ProjectLayout — add these methods
    def modules(self, context: str) -> tuple[str, ...]:
        base = self.src / context
        if not base.is_dir():
            return ()
        return tuple(
            sorted(
                p.name
                for p in base.iterdir()
                if p.is_dir()
                and p.name not in _CONTEXT_RESERVED
                and not p.name.startswith((".", "_"))
                and _has_layer(p)
            )
        )

    def module_domain_dir(self, context: str, module: str) -> Path:
        return self.src / context / module / "domain"

    def module_application_dir(self, context: str, module: str) -> Path:
        return self.src / context / module / "application"

    def module_infrastructure_dir(self, context: str, module: str) -> Path:
        return self.src / context / module / "infrastructure"

    def shared_dir(self, context: str) -> Path:
        return self.src / context / "shared"

    def read_dir(self, context: str) -> Path:
        return self.src / context / "read"

    def iter_modules(self) -> Iterator[tuple[str, str]]:
        for context in self.contexts:
            for module in self.modules(context):
                yield context, module
```

In `detect()`, replace the context predicate with:

```python
def _is_context(p: Path) -> bool:
    return (p / "entrypoints").is_dir() or _has_layer(p) or any(
        c.is_dir() and c.name not in _CONTEXT_RESERVED and _has_layer(c)
        for c in p.iterdir()
    )
```

and use `_is_context(p)` where the layer-dir check currently is.

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/checks/test_base.py -v && uv run mypy`
Expected: PASS, mypy clean. The whole suite must still be green (`uv run pytest`) — the old accessors are untouched.

- [ ] **Step 5: Commit**

```bash
git add src/arch_standard/checks/base.py tests/checks/test_base.py
git commit -m "feat: ProjectLayout learns the aggregate-module level"
```

---

## Task 2: `modular_project` fixture in the canonical shape

**Files:**
- Create: `tests/fixtures/modular_project/**`
- Test: `tests/checks/test_base.py`

**Interfaces:**
- Consumes: `ProjectLayout.detect`, `.modules`, `.iter_modules`.
- Produces: `tests/fixtures/modular_project/` — the reference *compliant* tree in the new shape. Every later task asserts against it. Two contexts so ARCH-012 and ARCH-050 have something real to check.

- [ ] **Step 1: Build the tree**

Every directory gets an `__init__.py` (empty is fine). Full file list:

```text
tests/fixtures/modular_project/
├── contexts.toml
└── src/
    ├── sales/
    │   ├── entrypoints/http.py
    │   ├── shared/ids.py
    │   ├── read/customer_overview.py
    │   ├── users/
    │   │   ├── domain/model/{user.py,value_objects.py,events.py,ports.py,exceptions.py}
    │   │   ├── application/user_service.py
    │   │   └── infrastructure/user_repository.py
    │   └── orders/
    │       ├── domain/model/{order.py,events.py,ports.py}
    │       ├── application/order_service.py
    │       └── infrastructure/order_repository.py
    └── billing/
        ├── entrypoints/http.py
        └── invoices/
            ├── domain/model/{invoice.py,events.py,ports.py}
            ├── application/invoice_service.py
            └── infrastructure/invoice_repository.py
```

Key file contents (the rest are `__init__.py` or a single class):

```toml
# tests/fixtures/modular_project/contexts.toml
[contexts.sales]
depends_on = ["billing"]

[contexts.billing]
depends_on = []
```

```python
# src/sales/shared/ids.py
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class UserId:
    value: str


@dataclass(frozen=True)
class OrderId:
    value: str
```

```python
# src/sales/users/domain/model/user.py
from __future__ import annotations

from dataclasses import dataclass, field

from sales.shared.ids import UserId


@dataclass
class User:
    id: UserId
    _emails: list[str] = field(default_factory=list)

    def add_email(self, email: str) -> None:
        self._emails.append(email)
```

```python
# src/sales/users/domain/model/events.py
from __future__ import annotations

import dataclasses
from datetime import datetime

from sales.shared.ids import UserId


@dataclasses.dataclass(frozen=True)
class UserRegistered:
    user_id: UserId
    occurred_at: datetime
```

```python
# src/sales/users/domain/model/value_objects.py
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Email:
    value: str

    def __post_init__(self) -> None:
        if "@" not in self.value:
            raise ValueError("invalid email")
```

```python
# src/sales/users/domain/model/ports.py
from __future__ import annotations

from typing import Protocol

from sales.shared.ids import UserId
from sales.users.domain.model.user import User


class UserRepository(Protocol):
    def get(self, user_id: UserId) -> User: ...
    def add(self, user: User) -> None: ...
```

```python
# src/sales/users/domain/model/exceptions.py
from __future__ import annotations


class UserNotFound(Exception):
    pass
```

```python
# src/sales/users/application/user_service.py
from __future__ import annotations

from dataclasses import dataclass

from sales.shared.ids import UserId
from sales.users.domain.model.ports import UserRepository
from sales.users.domain.model.user import User


@dataclass(frozen=True)
class RegisterUser:
    user_id: str


class UserService:
    def __init__(self, users: UserRepository) -> None:
        self._users = users

    def register_user(self, command: RegisterUser) -> None:
        self._users.add(User(id=UserId(command.user_id)))
```

```python
# src/sales/users/infrastructure/user_repository.py
from __future__ import annotations

from sales.shared.ids import UserId
from sales.users.domain.model.user import User


class InMemoryUserRepository:
    def __init__(self) -> None:
        self._store: dict[str, User] = {}

    def get(self, user_id: UserId) -> User:
        return self._store[user_id.value]

    def add(self, user: User) -> None:
        self._store[user.id.value] = user
```

```python
# src/sales/read/customer_overview.py
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class CustomerOverview:
    user_id: str
    order_count: int


def load_customer_overview(user_id: str) -> CustomerOverview:
    return CustomerOverview(user_id=user_id, order_count=0)
```

```python
# src/sales/entrypoints/http.py
from __future__ import annotations

from sales.read.customer_overview import load_customer_overview
from sales.users.application.user_service import RegisterUser, UserService


def register(service: UserService, user_id: str) -> None:
    service.register_user(RegisterUser(user_id=user_id))


def overview(user_id: str) -> object:
    return load_customer_overview(user_id)
```

`orders/` and `billing/invoices/` follow the same shapes with `Order`/`OrderId` and
`Invoice`/`InvoiceId` (put `InvoiceId` in `billing/shared/ids.py`; give `billing` a
`shared/` dir too). Every domain event class is a frozen dataclass named in the past tense.
No file imports a framework, calls `datetime.now()`, or inherits an ORM base.

- [ ] **Step 2: Write the failing test**

```python
# append to tests/checks/test_base.py
MODULAR = Path(__file__).parent.parent / "fixtures" / "modular_project"


def test_given_modular_fixture__when_detect__then_two_contexts() -> None:
    layout = ProjectLayout.detect(MODULAR)
    assert layout.contexts == ("billing", "sales")


def test_given_modular_fixture__when_iter_modules__then_all_aggregate_modules() -> None:
    layout = ProjectLayout.detect(MODULAR)
    assert list(layout.iter_modules()) == [
        ("billing", "invoices"),
        ("sales", "orders"),
        ("sales", "users"),
    ]
```

- [ ] **Step 3: Run to verify it fails, then build the tree, then verify it passes**

Run: `uv run pytest tests/checks/test_base.py -k modular_fixture -v`
Expected before: FAIL (`contexts == ()`). After building the tree: PASS.

- [ ] **Step 4: Verify the fixture is importable**

Run: `cd tests/fixtures/modular_project/src && python -c "import sales.users.application.user_service, sales.read.customer_overview, sales.entrypoints.http, billing.invoices.application.invoice_service"`
Expected: no output, exit 0. If it fails, an `__init__.py` is missing or an import is dangling — fix before proceeding. `ImportContractsCheck` (Task 6) genuinely imports this tree.

- [ ] **Step 5: Commit**

```bash
git add tests/fixtures/modular_project tests/checks/test_base.py
git commit -m "test: add modular_project fixture in the canonical aggregate-module shape"
```

---

## Task 3: Rule tiers + the eight new rules

**Files:**
- Modify: `src/arch_standard/rules/model.py`, `src/arch_standard/rules/catalog.py`
- Modify: `rules/dependencies.yaml`, `rules/model_integrity.yaml`, `rules/application.yaml`, `rules/cross_cutting.yaml`
- Create: `rules/structure.yaml`
- Test: `tests/rules/test_model.py`, `tests/rules/test_catalog.py`, `tests/rules/test_real_catalog.py`

**Interfaces:**
- Produces:
  - `Tier(StrEnum)` in `model.py` — `CORE = "core"`, `FULL = "full"`.
  - `Rule.tier: Tier = Tier.FULL` — optional in YAML, defaults to `full`.
  - `Catalog.core() -> list[Rule]` — rules with `tier is Tier.CORE`.
  - Eight new rules: ARCH-046, 047, 048, 049 (category `structure`, new file `rules/structure.yaml`), ARCH-050 (category `structure`), ARCH-051 (category `model_integrity`), ARCH-052 (`structure`), ARCH-053 (`cross_cutting`).
  - ARCH-024, ARCH-043, ARCH-044 levels change to `MUST*`.
  - Exactly 12 rules carry `tier: core`: ARCH-001, 002, 003, 005, 006, 008, 012, 021, 023, 031, 046, 051.

- [ ] **Step 1: Write the failing tests**

```python
# append to tests/rules/test_model.py
from arch_standard.rules.model import Tier


def test_given_no_tier__when_parsing_a_rule__then_defaults_to_full() -> None:
    rule = Rule(**_valid_kwargs())
    assert rule.tier is Tier.FULL


def test_given_core_tier__when_parsing_a_rule__then_tier_is_core() -> None:
    rule = Rule(**{**_valid_kwargs(), "tier": "core"})
    assert rule.tier is Tier.CORE
```

```python
# append to tests/rules/test_real_catalog.py
from arch_standard.rules.model import Level, Tier

CORE_IDS = {
    "ARCH-001", "ARCH-002", "ARCH-003", "ARCH-005", "ARCH-006", "ARCH-008",
    "ARCH-012", "ARCH-021", "ARCH-023", "ARCH-031", "ARCH-046", "ARCH-051",
}
NEW_IDS = {f"ARCH-{n:03d}" for n in range(46, 54)}


def test_given_the_catalog__when_loaded__then_the_new_rules_are_present() -> None:
    cat = Catalog.load(RULES_DIR)
    assert NEW_IDS <= {r.id for r in cat}


def test_given_the_catalog__when_filtering_core__then_exactly_the_twelve() -> None:
    cat = Catalog.load(RULES_DIR)
    assert {r.id for r in cat.core()} == CORE_IDS
    assert len(cat.core()) == 12


def test_given_the_catalog__when_reading_conditional_rules__then_they_are_must_star() -> None:
    cat = Catalog.load(RULES_DIR)
    for rid in ("ARCH-024", "ARCH-043", "ARCH-044"):
        assert cat.get(rid).level is Level.MUST_CONDITIONAL, rid


def test_given_a_core_rule__when_read__then_it_is_machine_checkable() -> None:
    cat = Catalog.load(RULES_DIR)
    for rule in cat.core():
        assert rule.validation.tool != "review", rule.id
```

- [ ] **Step 2: Run to verify they fail**

Run: `uv run pytest tests/rules -v`
Expected: FAIL — `Tier` not importable; new IDs missing.

- [ ] **Step 3: Add `Tier` to the model**

```python
# src/arch_standard/rules/model.py
class Tier(StrEnum):
    CORE = "core"
    FULL = "full"
```

Add to `Rule`: `tier: Tier = Tier.FULL`.

```python
# src/arch_standard/rules/catalog.py — add to Catalog
    def core(self) -> list[Rule]:
        return [r for r in self._rules if r.tier is Tier.CORE]
```

(import `Tier` alongside `Level`.)

- [ ] **Step 4: Write `rules/structure.yaml`**

Six rules, category `structure`. Full shape for each — this is the pattern; write all six:

```yaml
rules:
  - id: ARCH-046
    name: Aggregate module isolation
    level: MUST
    automation: full
    tier: core
    category: structure
    description: >
      An aggregate module does not import another aggregate module's application/ or
      infrastructure/ package. References between aggregates are by ID, and those ID
      types live in the context's shared/ids.py.
    rationale: >
      Aggregate modules are consistency boundaries. Reaching into a sibling's service or
      repository re-couples them and makes the one-transaction-one-aggregate rule
      unenforceable.
    correct: |
      # sales/orders/domain/model/order.py
      from sales.shared.ids import UserId
      class Order:
          customer_id: UserId
    incorrect: |
      # sales/orders/application/order_service.py
      from sales.users.application.user_service import UserService
    validation:
      tool: import-linter
      detail: forbidden contract between sibling modules' application and infrastructure
    related: [ARCH-020, ARCH-021]
  - id: ARCH-047
    name: Context shared area is strictly limited
    level: MUST
    automation: partial
    category: structure
    description: >
      <context>/shared/ contains only ID types, policy-free value objects used by two or
      more aggregates of that context, and domain services spanning them.
    rationale: >
      It is the only context-level code area, so without a narrow admission test it
      becomes the junk drawer that couples every aggregate module together.
    correct: |
      # sales/shared/ids.py
      @dataclass(frozen=True)
      class UserId:
          value: str
    incorrect: |
      # sales/shared/user_service.py
      class UserService: ...
    validation:
      tool: ast-checker
      detail: no class named *Service/*Repository, no aggregate roots
  - id: ARCH-048
    name: No context-level application package
    level: MUST
    automation: full
    category: structure
    description: >
      A context has no application/ package of its own. Application services live in
      aggregate modules, one per aggregate.
    rationale: >
      DDD has no "application service of the context"; application services are per use
      case and belong with the model they coordinate. A context-level one becomes a
      coordination layer that hides non-atomic multi-aggregate flow.
    correct: "sales/orders/application/order_service.py"
    incorrect: "sales/application/sales_service.py"
    validation:
      tool: ast-checker
      detail: filesystem check for <context>/application
  - id: ARCH-049
    name: One aggregate root per aggregate module
    level: MUST
    automation: partial
    category: structure
    description: >
      An aggregate module's domain/model/ declares exactly one aggregate root, in a file
      named after it.
    rationale: >
      The 1:1 mapping is what makes "where does this go?" answerable without judgement,
      and it makes the transaction boundary visible in the tree.
    correct: "sales/users/domain/model/user.py declaring class User"
    incorrect: "sales/users/domain/model/user.py declaring class User and class Order"
    validation:
      tool: ast-checker
      detail: exactly one non-reserved module in domain/model
  - id: ARCH-050
    name: Declared context dependency graph
    level: MUST
    automation: full
    category: structure
    description: >
      Every cross-context dependency is declared in contexts.toml, and the declared graph
      is acyclic.
    rationale: >
      Contexts never import each other, so no import analysis can see a runtime cycle
      wired through the composition root. Declaring the graph is the only way to check it,
      and it turns adding an edge into a reviewable diff.
    correct: |
      # contexts.toml
      [contexts.sales]
      depends_on = ["billing"]
    incorrect: |
      [contexts.sales]
      depends_on = ["billing"]
      [contexts.billing]
      depends_on = ["sales"]
    validation:
      tool: schema
      detail: parse contexts.toml, topological sort
  - id: ARCH-052
    name: Read layer does not import the write side
    level: MUST
    automation: full
    category: structure
    description: >
      <context>/read/ imports no aggregate module's domain/ or application/ package.
    rationale: >
      The read layer exists to answer queries the write model is not shaped for. Importing
      the write side re-couples them and pulls invariant-carrying objects into query paths.
    correct: |
      # sales/read/customer_overview.py
      @dataclass(frozen=True)
      class CustomerOverview:
          user_id: str
    incorrect: |
      # sales/read/customer_overview.py
      from sales.users.domain.model.user import User
    validation:
      tool: import-linter
      detail: forbidden contract read -> modules' domain/application
```

- [ ] **Step 5: Add ARCH-051 and ARCH-053, and set tiers and MUST\***

Append to `rules/model_integrity.yaml`:

```yaml
  - id: ARCH-051
    name: Repositories are not query interfaces
    level: MUST
    automation: partial
    tier: core
    category: model_integrity
    description: >
      Repositories persist and retrieve aggregate roots. They are not general-purpose
      query interfaces: projection-oriented, reporting, search, dashboard, and
      cross-aggregate reads belong to the context's read/ layer.
    rationale: >
      A repository that grows report queries stops being a collection of roots, drags
      query pressure into the write model, and starts returning DTOs instead of
      aggregates.
    correct: |
      class OrderRepository(Protocol):
          def get(self, order_id: OrderId) -> Order: ...
          def add(self, order: Order) -> None: ...
    incorrect: |
      class OrderRepository(Protocol):
          def find_premium_customers_with_overdue_invoices(self) -> list[ReportRow]: ...
    validation:
      tool: ast-checker
      detail: repository methods returning non-aggregate collections
    related: [ARCH-022, ARCH-052]
```

Append to `rules/cross_cutting.yaml`:

```yaml
  - id: ARCH-053
    name: The core does not log
    level: MUST
    automation: full
    category: cross_cutting
    description: >
      Modules under domain/ and application/ import no logging library and make no
      logging calls. They raise domain exceptions and emit domain events; entrypoints and
      infrastructure adapters log.
    rationale: >
      Logging is an observability concern of the adapters. Keeping it out of the core
      keeps the core free of ambient I/O and makes behavior fully assertable from the
      state and events a use case produces.
    correct: |
      # application: emit a fact
      self._bus.publish_all(self._uow.collect_new_events())
    incorrect: |
      # application
      import logging
      logging.getLogger(__name__).info("order created")
    validation:
      tool: ruff
      detail: banned logging imports/calls under domain/ and application/
```

Then add `tier: core` to ARCH-001, 002, 003, 005, 006, 008, 012, 021, 023, 031 in their existing files, and change `level: MUST` → `level: "MUST*"` for ARCH-024, ARCH-043, ARCH-044.

> `MUST*` must be quoted in YAML — an unquoted `MUST*` is still a valid plain scalar, but quote it for clarity and to avoid alias confusion.

- [ ] **Step 6: Run to verify green**

Run: `uv run pytest tests/rules -v && uv run mypy`
Expected: PASS. `Catalog.load` sees 53 rules; `core()` returns exactly the 12.

- [ ] **Step 7: Commit**

```bash
git add src/arch_standard/rules rules tests/rules
git commit -m "feat: rule tiers and the aggregate-module, read-layer and context-graph rules"
```

---

## Task 4: `BannedSymbolsCheck` walks aggregate modules; adds ARCH-053

**Files:**
- Modify: `src/arch_standard/checks/banned_symbols.py`
- Test: `tests/checks/test_banned_symbols.py`

**Interfaces:**
- Consumes: `ProjectLayout.iter_modules`, `.module_domain_dir`, `.module_application_dir`, `.shared_dir`, `outcome_for`, `Catalog`.
- Produces: `BannedSymbolsCheck.rule_ids = ("ARCH-003", "ARCH-004", "ARCH-028", "ARCH-053")`.
  - `_core_files(project)` — every `.py` under each module's `domain/` **and** `application/`, plus each context's `shared/`.
  - ARCH-003/004/028 keep their current meaning but scan `_domain_files` = module `domain/` dirs + `shared/`.
  - ARCH-053: banned logging under module `domain/` **and** `application/` — imports of `logging`/`structlog`/`loguru`, and any call whose dotted target starts with `logging.` or ends in `.debug`/`.info`/`.warning`/`.error`/`.exception`/`.critical` on a name containing `log`.

- [ ] **Step 1: Add the fixture violation**

```python
# tests/fixtures/bad_project/src/sales/domain/model/noisy.py  (kept at the OLD path until Task 10)
from __future__ import annotations

import logging  # ARCH-053

logger = logging.getLogger(__name__)


def announce() -> None:
    logger.info("something happened")
```

- [ ] **Step 2: Write the failing test**

```python
# append to tests/checks/test_banned_symbols.py
def test_given_a_logging_domain_module__when_checked__then_arch_053_fails() -> None:
    r = _reports("bad_project")["ARCH-053"]
    assert r.outcome is Outcome.FAIL
    assert any("logging" in f.message for f in r.findings)


def test_given_the_modular_fixture__when_checked__then_all_banned_symbol_rules_pass() -> None:
    layout = ProjectLayout.detect(FIX / "modular_project")
    reports = {r.rule_id: r for r in BannedSymbolsCheck().run(layout, Catalog.load(RULES))}
    assert all(r.outcome is Outcome.PASS for r in reports.values())
```

- [ ] **Step 3: Run to verify it fails**

Run: `uv run pytest tests/checks/test_banned_symbols.py -v`
Expected: FAIL — `KeyError: 'ARCH-053'`, and the modular fixture reports nothing because `_domain_files` only walks the old paths.

- [ ] **Step 4: Implement**

```python
# src/arch_standard/checks/banned_symbols.py
DEFAULT_BANNED_LOGGING = frozenset({"logging", "structlog", "loguru"})
_LOG_METHODS = frozenset({"debug", "info", "warning", "warn", "error", "exception", "critical"})


def _domain_files(project: ProjectLayout) -> list[Path]:
    files: list[Path] = []
    for context, module in project.iter_modules():
        files.extend(iter_python_files(project.module_domain_dir(context, module)))
    for context in project.contexts:
        files.extend(iter_python_files(project.shared_dir(context)))
        # legacy single-level layout, removed in Task 10
        files.extend(iter_python_files(project.domain_dir(context)))
    return files


def _core_files(project: ProjectLayout) -> list[Path]:
    files = _domain_files(project)
    for context, module in project.iter_modules():
        files.extend(iter_python_files(project.module_application_dir(context, module)))
    return files
```

In `run`, add a fourth accumulator and a second pass:

```python
        logging_findings: list[Finding] = []
        for path in _core_files(project):
            rel = str(path.relative_to(project.root))
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        if alias.name.split(".")[0] in DEFAULT_BANNED_LOGGING:
                            logging_findings.append(
                                Finding("ARCH-053", rel, node.lineno, f"core imports {alias.name}")
                            )
                elif isinstance(node, ast.ImportFrom) and node.module:
                    if node.module.split(".")[0] in DEFAULT_BANNED_LOGGING:
                        logging_findings.append(
                            Finding("ARCH-053", rel, node.lineno, f"core imports {node.module}")
                        )
                elif isinstance(node, ast.Call):
                    target = _dotted(node.func)
                    head, _, method = target.rpartition(".")
                    if method in _LOG_METHODS and "log" in head.lower():
                        logging_findings.append(
                            Finding("ARCH-053", rel, node.lineno, f"core logs via {target}")
                        )
```

Return it through `outcome_for(catalog.get("ARCH-053").level, bool(logging_findings))`, same as the other three.

- [ ] **Step 5: Run to verify green**

Run: `uv run pytest tests/checks/test_banned_symbols.py -v && uv run pytest && uv run mypy`
Expected: PASS, full suite green.

- [ ] **Step 6: Commit**

```bash
git add src/arch_standard/checks/banned_symbols.py tests
git commit -m "feat: banned-symbols walks aggregate modules and enforces ARCH-053"
```

---

## Task 5: `AstRulesCheck` walks aggregate modules; adds ARCH-049

**Files:**
- Modify: `src/arch_standard/checks/ast_rules.py`
- Test: `tests/checks/test_ast_rules.py`

**Interfaces:**
- Consumes: `ProjectLayout.iter_modules`, `.module_domain_dir`, `.module_application_dir`.
- Produces: `AstRulesCheck.rule_ids` gains `"ARCH-049"`.
  - `_RESERVED_MODEL_FILES = frozenset({"__init__", "value_objects", "events", "ports", "exceptions", "projections"})`
  - `_aggregate_files(project, context, module) -> list[Path]` — every `.py` in `<module>/domain/model/` whose stem is not reserved. **This is the aggregate file; there is no `aggregates.py` any more.**
  - `_check_domain_events` / `_check_value_objects` now iterate `iter_modules()` and read `<module>/domain/model/events.py` and `value_objects.py`.
  - `_check_aggregate_encapsulation` reads the aggregate files instead of `aggregates.py`.
  - `_check_service_size` walks `module_application_dir`.
  - `_check_promotion_thresholds` uses the Section 15 signals: aggregate file > 400 lines, `ports.py` > 8 protocols.
  - `_check_one_aggregate_per_module` (ARCH-049) — FAIL if a module's `domain/model/` has zero or more than one aggregate file, or if an aggregate file declares more than one non-dataclass-frozen class.

- [ ] **Step 1: Write the failing test**

```python
# append to tests/checks/test_ast_rules.py
def test_given_the_modular_fixture__when_checked__then_all_ast_rules_pass() -> None:
    layout = ProjectLayout.detect(FIX / "modular_project")
    reports = {r.rule_id: r for r in AstRulesCheck().run(layout, Catalog.load(RULES))}
    for rid in ("ARCH-018", "ARCH-019", "ARCH-023", "ARCH-031", "ARCH-049"):
        assert reports[rid].outcome is Outcome.PASS, rid


def test_given_a_module_with_two_aggregate_files__when_checked__then_arch_049_fails(
    tmp_path: Path,
) -> None:
    root = tmp_path / "p"
    model = root / "src/sales/users/domain/model"
    model.mkdir(parents=True)
    (root / "src/sales/users/application").mkdir(parents=True)
    (model / "user.py").write_text("class User:\n    pass\n", encoding="utf-8")
    (model / "profile.py").write_text("class Profile:\n    pass\n", encoding="utf-8")
    layout = ProjectLayout.detect(root)
    reports = {r.rule_id: r for r in AstRulesCheck().run(layout, Catalog.load(RULES))}
    assert reports["ARCH-049"].outcome is Outcome.FAIL
```

- [ ] **Step 2: Run to verify it fails**

Run: `uv run pytest tests/checks/test_ast_rules.py -k "modular or 049" -v`
Expected: FAIL — `KeyError: 'ARCH-049'`.

- [ ] **Step 3: Implement**

```python
_RESERVED_MODEL_FILES = frozenset(
    {"__init__", "value_objects", "events", "ports", "exceptions", "projections"}
)


def _aggregate_files(project: ProjectLayout, context: str, module: str) -> list[Path]:
    model = project.module_domain_dir(context, module) / "model"
    if not model.is_dir():
        return []
    return sorted(p for p in model.glob("*.py") if p.stem not in _RESERVED_MODEL_FILES)


def _check_one_aggregate_per_module(project: ProjectLayout) -> list[Finding]:
    findings: list[Finding] = []
    for context, module in project.iter_modules():
        files = _aggregate_files(project, context, module)
        rel = f"src/{context}/{module}/domain/model"
        if len(files) == 0:
            findings.append(
                Finding("ARCH-049", rel, None, f"{module} declares no aggregate root")
            )
        elif len(files) > 1:
            names = ", ".join(f.name for f in files)
            findings.append(
                Finding("ARCH-049", rel, None, f"{module} declares more than one aggregate: {names}")
            )
    return findings
```

Rewrite `_check_domain_events`, `_check_value_objects`, `_check_aggregate_encapsulation`,
`_check_service_size` and `_check_promotion_thresholds` to iterate
`for context, module in project.iter_modules():` and use the module-scoped path helpers.
`_check_aggregate_encapsulation` iterates `_aggregate_files(...)` instead of `aggregates.py`.
Register `"ARCH-049": _check_one_aggregate_per_module` in `_IMPLEMENTED` and add
`"ARCH-049"` to `rule_ids`.

- [ ] **Step 4: Run to verify green**

Run: `uv run pytest tests/checks/test_ast_rules.py -v && uv run mypy`
Expected: PASS. Some existing bad_project assertions may now report `PASS` because the old
paths are no longer scanned — that is expected; those fixtures migrate in Task 10. If an
assertion breaks, mark it `@pytest.mark.xfail(reason="fixture migrates in Task 10")` rather
than weakening it, and remove the marker in Task 10.

- [ ] **Step 5: Commit**

```bash
git add src/arch_standard/checks/ast_rules.py tests/checks/test_ast_rules.py
git commit -m "feat: AST checks walk aggregate modules and enforce one aggregate per module"
```

---

## Task 6: `ImportContractsCheck` per-module layers, ARCH-046 and ARCH-052

**Files:**
- Modify: `src/arch_standard/checks/import_contracts.py`
- Test: `tests/checks/test_import_contracts.py`

**Interfaces:**
- Produces: `rule_ids` gains `"ARCH-046"` and `"ARCH-052"`.
  - `build_contracts` emits, per context: one **layers** contract per aggregate module
    (`<ctx>.<mod>.infrastructure` → `<ctx>.<mod>.application` → `<ctx>.<mod>.domain`, each in
    optional-layer parens); one **forbidden** contract `ARCH-046` per context whose sources are
    each module and whose forbidden modules are the *other* modules' `application` and
    `infrastructure`; one **forbidden** contract `ARCH-052` per context with `read` as source
    and every module's `domain`/`application` forbidden. The existing `ARCH-012` independence
    contract between contexts and the `ARCH-034`/`ARCH-035` commons contracts stay.
  - `entrypoints` is no longer in the per-module layers contract — it sits above all modules
    and is covered by ARCH-009/011.

- [ ] **Step 1: Write the failing test**

```python
# append to tests/checks/test_import_contracts.py
MODULAR = FIX / "modular_project"


def test_given_the_modular_fixture__when_building_contracts__then_module_layers_are_emitted() -> None:
    ini = build_contracts(ProjectLayout.detect(MODULAR))
    assert "sales.users.domain" in ini
    assert "[importlinter:contract:ARCH-046-sales]" in ini
    assert "[importlinter:contract:ARCH-052-sales]" in ini


def test_given_the_modular_fixture__when_checked__then_every_rule_passes() -> None:
    layout = ProjectLayout.detect(MODULAR)
    reports = ImportContractsCheck().run(layout, Catalog.load(RULES))
    assert all(r.outcome is Outcome.PASS for r in reports), [
        (r.rule_id, [f.message for f in r.findings]) for r in reports if r.outcome is not Outcome.PASS
    ]
```

- [ ] **Step 2: Run to verify it fails**

Run: `uv run pytest tests/checks/test_import_contracts.py -k modular -v`
Expected: FAIL — the ARCH-046/052 contract sections are absent.

- [ ] **Step 3: Implement**

```python
_MODULE_LAYERS = ("infrastructure", "application", "domain")


def _module_contracts(project: ProjectLayout, context: str) -> list[str]:
    modules = project.modules(context)
    if not modules:
        return []
    lines: list[str] = []
    for module in modules:
        lines += [
            f"[importlinter:contract:ARCH-layers-{context}-{module}]",
            f"name = ARCH-001/002/005/006 layered ({context}.{module})",
            "type = layers",
            "layers =",
            *(f"    ({context}.{module}.{layer})" for layer in _MODULE_LAYERS),
            "",
        ]
    if len(modules) > 1:
        forbidden = [
            f"    {context}.{m}.{layer}" for m in modules for layer in ("application", "infrastructure")
        ]
        lines += [
            f"[importlinter:contract:ARCH-046-{context}]",
            f"name = ARCH-046 aggregate module isolation ({context})",
            "type = forbidden",
            "source_modules =",
            *(f"    {context}.{m}" for m in modules),
            "forbidden_modules =",
            *forbidden,
            "unmatched_ignore_imports_alerting = none",
            "",
        ]
    if (project.read_dir(context)).is_dir():
        lines += [
            f"[importlinter:contract:ARCH-052-{context}]",
            f"name = ARCH-052 read layer does not import the write side ({context})",
            "type = forbidden",
            "source_modules =",
            f"    {context}.read",
            "forbidden_modules =",
            *(f"    {context}.{m}.{layer}" for m in modules for layer in ("domain", "application")),
            "",
        ]
    return lines
```

Call `_module_contracts(project, context)` from `build_contracts` for every context, and keep
the existing single-level layers contract only when `project.modules(context)` is empty
(legacy fixtures; deleted in Task 10). Add `"ARCH-046"` and `"ARCH-052"` to `rule_ids`, and
extend `_parse_broken_rules` so a broken `ARCH-046-<ctx>` or `ARCH-052-<ctx>` contract name
maps back to the bare rule id (strip everything from the second hyphen after `ARCH`).

> **A forbidden contract listing a module as both source and forbidden will report itself
> broken.** Exclude each module's own layers from its forbidden list, or use one contract per
> source module. Verify by hand (Step 4) before trusting the test.

- [ ] **Step 4: Verify by hand against the real tool**

Run:
```bash
cd tests/fixtures/modular_project/src
PYTHONPATH=. python -c "
from pathlib import Path
import sys; sys.path.insert(0, '../../../../src')
from arch_standard.checks.base import ProjectLayout
from arch_standard.checks.import_contracts import build_contracts
Path('/tmp/ml.ini').write_text(build_contracts(ProjectLayout.detect(Path('..'))))
"
PYTHONPATH=. lint-imports --config /tmp/ml.ini --no-cache
```
Expected: every contract KEPT, exit 0. If a contract errors ("could not find package"),
fix the INI generation before proceeding — an errored run maps to FAIL-all and the test
would pass for the wrong reason.

Then add a deliberate violation (`sales/read/customer_overview.py` importing
`sales.users.domain.model.user`), re-run, and confirm **only** `ARCH-052-sales` is BROKEN.
Revert the violation.

- [ ] **Step 5: Run tests and commit**

Run: `uv run pytest tests/checks/test_import_contracts.py -v && uv run pytest && uv run mypy`

```bash
git add src/arch_standard/checks/import_contracts.py tests/checks/test_import_contracts.py
git commit -m "feat: import contracts for aggregate-module layers, ARCH-046 and ARCH-052"
```

---

## Task 7: `StructureCheck` — ARCH-047, ARCH-048, ARCH-051

**Files:**
- Create: `src/arch_standard/checks/structure.py`
- Modify: `src/arch_standard/checks/__init__.py`
- Test: `tests/checks/test_structure.py`

**Interfaces:**
- Produces: `class StructureCheck` with `rule_ids = ("ARCH-047", "ARCH-048", "ARCH-051")` and the standard `run(project, catalog) -> list[CheckReport]`.
  - **ARCH-048** (filesystem): FAIL if `<src>/<context>/application` is a directory.
  - **ARCH-047** (AST over `<context>/shared/**/*.py`): FAIL for any class whose name ends in `Service` or `Repository`, and for any class that mutates state (has a non-dunder method assigning to `self.<attr>`) — a proxy for "this is an aggregate, not a value object".
  - **ARCH-051** (AST over each module's `domain/model/ports.py`): FAIL for a method on a `Protocol` class whose name ends in `Repository` when the method name starts with `find_`/`search_`/`list_`/`report_`/`query_` **and** its return annotation is a `list`/`Sequence`/`Iterable` of something that is not the module's aggregate type.

- [ ] **Step 1: Write the failing test**

```python
# tests/checks/test_structure.py
from __future__ import annotations

from pathlib import Path

from arch_standard.checks.base import Outcome, ProjectLayout
from arch_standard.checks.structure import StructureCheck
from arch_standard.rules.catalog import Catalog

FIX = Path(__file__).parent.parent / "fixtures"
RULES = Path(__file__).parent.parent.parent / "rules"


def _reports(root: Path) -> dict[str, object]:
    return {r.rule_id: r for r in StructureCheck().run(ProjectLayout.detect(root), Catalog.load(RULES))}


def test_given_the_modular_fixture__when_checked__then_structure_rules_pass() -> None:
    reports = _reports(FIX / "modular_project")
    for rid in ("ARCH-047", "ARCH-048", "ARCH-051"):
        assert reports[rid].outcome is Outcome.PASS, rid


def test_given_a_context_level_application_dir__when_checked__then_arch_048_fails(
    tmp_path: Path,
) -> None:
    root = tmp_path / "p"
    (root / "src/sales/entrypoints").mkdir(parents=True)
    (root / "src/sales/application").mkdir(parents=True)
    (root / "src/sales/users/domain/model").mkdir(parents=True)
    (root / "src/sales/users/domain/model/user.py").write_text("class User: pass\n", encoding="utf-8")
    assert _reports(root)["ARCH-048"].outcome is Outcome.FAIL


def test_given_a_service_in_shared__when_checked__then_arch_047_fails(tmp_path: Path) -> None:
    root = tmp_path / "p"
    (root / "src/sales/shared").mkdir(parents=True)
    (root / "src/sales/users/domain/model").mkdir(parents=True)
    (root / "src/sales/users/domain/model/user.py").write_text("class User: pass\n", encoding="utf-8")
    (root / "src/sales/shared/helpers.py").write_text(
        "class UserService:\n    pass\n", encoding="utf-8"
    )
    assert _reports(root)["ARCH-047"].outcome is Outcome.FAIL


def test_given_a_reporting_method_on_a_repository_port__when_checked__then_arch_051_fails(
    tmp_path: Path,
) -> None:
    root = tmp_path / "p"
    model = root / "src/sales/orders/domain/model"
    model.mkdir(parents=True)
    (model / "order.py").write_text("class Order: pass\n", encoding="utf-8")
    (model / "ports.py").write_text(
        "from typing import Protocol\n"
        "class OrderRepository(Protocol):\n"
        "    def find_overdue_report(self) -> list[dict]: ...\n",
        encoding="utf-8",
    )
    assert _reports(root)["ARCH-051"].outcome is Outcome.FAIL
```

- [ ] **Step 2: Run to verify it fails**

Run: `uv run pytest tests/checks/test_structure.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'arch_standard.checks.structure'`

- [ ] **Step 3: Implement `structure.py`**

```python
from __future__ import annotations

import ast
from pathlib import Path

from arch_standard.checks.base import (
    CheckReport,
    Finding,
    ProjectLayout,
    iter_python_files,
    outcome_for,
)
from arch_standard.rules.catalog import Catalog

_QUERY_PREFIXES = ("find_", "search_", "list_", "report_", "query_")
_COLLECTION_ROOTS = {"list", "List", "Sequence", "Iterable", "tuple", "set"}


def _classes(path: Path) -> list[ast.ClassDef]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    return [n for n in ast.walk(tree) if isinstance(n, ast.ClassDef)]


def _mutates_self(cls: ast.ClassDef) -> bool:
    for node in ast.walk(cls):
        if isinstance(node, ast.FunctionDef) and not node.name.startswith("__"):
            for stmt in ast.walk(node):
                if isinstance(stmt, ast.Assign):
                    for tgt in stmt.targets:
                        if (
                            isinstance(tgt, ast.Attribute)
                            and isinstance(tgt.value, ast.Name)
                            and tgt.value.id == "self"
                        ):
                            return True
    return False


def _check_no_context_application(project: ProjectLayout) -> list[Finding]:
    findings: list[Finding] = []
    for context in project.contexts:
        path = project.src / context / "application"
        if path.is_dir():
            findings.append(
                Finding(
                    "ARCH-048",
                    str(path.relative_to(project.root)),
                    None,
                    f"{context} has a context-level application/ package",
                )
            )
    return findings


def _check_shared_is_limited(project: ProjectLayout) -> list[Finding]:
    findings: list[Finding] = []
    for context in project.contexts:
        for path in iter_python_files(project.shared_dir(context)):
            rel = str(path.relative_to(project.root))
            for cls in _classes(path):
                if cls.name.endswith(("Service", "Repository")):
                    findings.append(
                        Finding("ARCH-047", rel, cls.lineno, f"{cls.name} does not belong in shared/")
                    )
                elif _mutates_self(cls):
                    findings.append(
                        Finding(
                            "ARCH-047",
                            rel,
                            cls.lineno,
                            f"{cls.name} mutates its own state; shared/ holds value objects",
                        )
                    )
    return findings


def _annotation_root(node: ast.expr | None) -> str | None:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Subscript):
        return _annotation_root(node.value)
    return None


def _check_repositories_are_not_queries(project: ProjectLayout) -> list[Finding]:
    findings: list[Finding] = []
    for context, module in project.iter_modules():
        ports = project.module_domain_dir(context, module) / "model" / "ports.py"
        if not ports.exists():
            continue
        rel = str(ports.relative_to(project.root))
        for cls in _classes(ports):
            if not cls.name.endswith("Repository"):
                continue
            for stmt in cls.body:
                if not isinstance(stmt, ast.FunctionDef):
                    continue
                if not stmt.name.startswith(_QUERY_PREFIXES):
                    continue
                if _annotation_root(stmt.returns) in _COLLECTION_ROOTS:
                    findings.append(
                        Finding(
                            "ARCH-051",
                            rel,
                            stmt.lineno,
                            f"{cls.name}.{stmt.name} is a query, not aggregate retrieval; "
                            f"move it to {context}/read/",
                        )
                    )
    return findings


class StructureCheck:
    rule_ids: tuple[str, ...] = ("ARCH-047", "ARCH-048", "ARCH-051")

    def run(self, project: ProjectLayout, catalog: Catalog) -> list[CheckReport]:
        by_rule = {
            "ARCH-047": _check_shared_is_limited(project),
            "ARCH-048": _check_no_context_application(project),
            "ARCH-051": _check_repositories_are_not_queries(project),
        }
        return [
            CheckReport(
                rule_id=rid,
                outcome=outcome_for(catalog.get(rid).level, bool(findings)),
                findings=tuple(findings),
            )
            for rid, findings in by_rule.items()
        ]
```

Register it in `checks/__init__.py`'s `all_checks()`.

- [ ] **Step 4: Run to verify green and commit**

Run: `uv run pytest tests/checks/test_structure.py -v && uv run pytest && uv run mypy`

```bash
git add src/arch_standard/checks/structure.py src/arch_standard/checks/__init__.py tests/checks/test_structure.py
git commit -m "feat: structure check for shared/, context application/, and repository queries"
```

---

## Task 8: `ContextGraphCheck` — ARCH-050

**Files:**
- Create: `src/arch_standard/checks/context_graph.py`
- Modify: `src/arch_standard/checks/__init__.py`
- Test: `tests/checks/test_context_graph.py`

**Interfaces:**
- Produces: `class ContextGraphCheck` with `rule_ids = ("ARCH-050",)`.
  - Reads `<root>/contexts.toml` with `tomllib`. Shape: `[contexts.<name>] depends_on = [<name>, ...]`.
  - `SKIP` when the file is absent **and** the project has fewer than 2 contexts (a single-context project has no graph to declare). `FAIL` when the file is absent and there are 2+ contexts.
  - `FAIL` when a declared context is not a detected context, when a detected context is undeclared, when `depends_on` names an unknown context, or when the graph has a cycle (report the cycle path).
  - `find_cycle(graph: dict[str, list[str]]) -> list[str] | None` — DFS with a colour map; returns the cycle as a list of node names, or `None`.

- [ ] **Step 1: Write the failing test**

```python
# tests/checks/test_context_graph.py
from __future__ import annotations

from pathlib import Path

from arch_standard.checks.base import Outcome, ProjectLayout
from arch_standard.checks.context_graph import ContextGraphCheck, find_cycle
from arch_standard.rules.catalog import Catalog

FIX = Path(__file__).parent.parent / "fixtures"
RULES = Path(__file__).parent.parent.parent / "rules"


def _report(root: Path):  # type: ignore[no-untyped-def]
    return ContextGraphCheck().run(ProjectLayout.detect(root), Catalog.load(RULES))[0]


def test_given_an_acyclic_graph__when_searching__then_no_cycle() -> None:
    assert find_cycle({"a": ["b"], "b": []}) is None


def test_given_a_cyclic_graph__when_searching__then_the_cycle_is_returned() -> None:
    cycle = find_cycle({"a": ["b"], "b": ["a"]})
    assert cycle is not None
    assert set(cycle) == {"a", "b"}


def test_given_the_modular_fixture__when_checked__then_arch_050_passes() -> None:
    assert _report(FIX / "modular_project").outcome is Outcome.PASS


def test_given_two_contexts_and_no_manifest__when_checked__then_arch_050_fails(
    tmp_path: Path,
) -> None:
    root = tmp_path / "p"
    for ctx in ("sales", "billing"):
        (root / f"src/{ctx}/entrypoints").mkdir(parents=True)
    r = _report(root)
    assert r.outcome is Outcome.FAIL
    assert any("contexts.toml" in f.message for f in r.findings)


def test_given_a_cyclic_manifest__when_checked__then_arch_050_fails(tmp_path: Path) -> None:
    root = tmp_path / "p"
    for ctx in ("sales", "billing"):
        (root / f"src/{ctx}/entrypoints").mkdir(parents=True)
    (root / "contexts.toml").write_text(
        '[contexts.sales]\ndepends_on = ["billing"]\n'
        '[contexts.billing]\ndepends_on = ["sales"]\n',
        encoding="utf-8",
    )
    r = _report(root)
    assert r.outcome is Outcome.FAIL
    assert any("cycle" in f.message.lower() for f in r.findings)


def test_given_one_context_and_no_manifest__when_checked__then_arch_050_skips(
    tmp_path: Path,
) -> None:
    root = tmp_path / "p"
    (root / "src/sales/entrypoints").mkdir(parents=True)
    assert _report(root).outcome is Outcome.SKIP
```

- [ ] **Step 2: Run to verify it fails**

Run: `uv run pytest tests/checks/test_context_graph.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'arch_standard.checks.context_graph'`

- [ ] **Step 3: Implement**

```python
from __future__ import annotations

import tomllib
from pathlib import Path

from arch_standard.checks.base import CheckReport, Finding, Outcome, ProjectLayout, outcome_for
from arch_standard.rules.catalog import Catalog

_MANIFEST = "contexts.toml"


def find_cycle(graph: dict[str, list[str]]) -> list[str] | None:
    WHITE, GREY, BLACK = 0, 1, 2
    colour = dict.fromkeys(graph, WHITE)
    stack: list[str] = []

    def visit(node: str) -> list[str] | None:
        colour[node] = GREY
        stack.append(node)
        for nxt in graph.get(node, []):
            if colour.get(nxt, WHITE) == GREY:
                return stack[stack.index(nxt) :] + [nxt]
            if colour.get(nxt, WHITE) == WHITE:
                found = visit(nxt)
                if found:
                    return found
        stack.pop()
        colour[node] = BLACK
        return None

    for node in sorted(graph):
        if colour[node] == WHITE:
            found = visit(node)
            if found:
                return found
    return None


def _load_manifest(path: Path) -> dict[str, list[str]]:
    raw = tomllib.loads(path.read_text(encoding="utf-8"))
    contexts = raw.get("contexts", {})
    return {name: list(cfg.get("depends_on", [])) for name, cfg in contexts.items()}


class ContextGraphCheck:
    rule_ids: tuple[str, ...] = ("ARCH-050",)

    def run(self, project: ProjectLayout, catalog: Catalog) -> list[CheckReport]:
        manifest = project.root / _MANIFEST
        detected = set(project.contexts)
        if not manifest.exists():
            if len(detected) < 2:
                return [CheckReport(rule_id="ARCH-050", outcome=Outcome.SKIP)]
            f = Finding(
                "ARCH-050", _MANIFEST, None,
                f"{_MANIFEST} is missing but the project has {len(detected)} contexts",
            )
            return [CheckReport("ARCH-050", outcome_for(catalog.get("ARCH-050").level, True), (f,))]

        graph = _load_manifest(manifest)
        findings: list[Finding] = []
        for name in sorted(set(graph) - detected):
            findings.append(Finding("ARCH-050", _MANIFEST, None, f"declared context {name!r} does not exist"))
        for name in sorted(detected - set(graph)):
            findings.append(Finding("ARCH-050", _MANIFEST, None, f"context {name!r} is not declared"))
        for name, deps in sorted(graph.items()):
            for dep in deps:
                if dep not in graph:
                    findings.append(
                        Finding("ARCH-050", _MANIFEST, None, f"{name} depends on undeclared context {dep!r}")
                    )
        cycle = find_cycle(graph)
        if cycle:
            findings.append(
                Finding("ARCH-050", _MANIFEST, None, f"context dependency cycle: {' -> '.join(cycle)}")
            )
        return [
            CheckReport(
                rule_id="ARCH-050",
                outcome=outcome_for(catalog.get("ARCH-050").level, bool(findings)),
                findings=tuple(findings),
            )
        ]
```

Register it in `all_checks()`.

- [ ] **Step 4: Run to verify green and commit**

Run: `uv run pytest tests/checks/test_context_graph.py -v && uv run pytest && uv run mypy`

```bash
git add src/arch_standard/checks/context_graph.py src/arch_standard/checks/__init__.py tests/checks/test_context_graph.py
git commit -m "feat: context dependency graph check (ARCH-050)"
```

---

## Task 9: `--core` flag

**Files:**
- Modify: `src/arch_standard/report.py`, `src/arch_standard/cli.py`
- Test: `tests/test_report.py`, `tests/test_cli.py`

**Interfaces:**
- Produces:
  - `Report.only(rule_ids: set[str]) -> Report` — a new `Report` keeping only reports whose `rule_id` is in the set.
  - `cli`: `arch-standard check [PATH] [--core]`. When `--core` is passed, `_run_check` filters the collected report with `report.only({r.id for r in catalog.core()})` **before** applying waivers and computing the exit code.
  - `format_text` footer gains a leading line naming the mode: `"core rules only (12)"` when filtered, nothing otherwise. Implement as an optional `header: str | None = None` parameter on `format_text`, defaulting to `None`.

- [ ] **Step 1: Write the failing test**

```python
# append to tests/test_report.py
def test_given_a_report__when_filtered_to_a_subset__then_only_those_remain() -> None:
    report = Report(
        reports=(
            CheckReport(rule_id="ARCH-001", outcome=Outcome.PASS),
            CheckReport(rule_id="ARCH-041", outcome=Outcome.WARN),
        )
    )
    assert {r.rule_id for r in report.only({"ARCH-001"}).reports} == {"ARCH-001"}
```

```python
# append to tests/test_cli.py
def test_given_core_mode__when_checking__then_only_core_rules_are_reported(
    capsys: pytest.CaptureFixture[str],
) -> None:
    from arch_standard.cli import main

    assert main(["check", str(FIX / "modular_project"), "--core"]) == 0
    out = capsys.readouterr().out
    assert "core rules only" in out
    assert "ARCH-041" not in out
```

- [ ] **Step 2: Run to verify it fails**

Run: `uv run pytest tests/test_report.py tests/test_cli.py -k "subset or core" -v`
Expected: FAIL — `AttributeError: 'Report' object has no attribute 'only'`.

- [ ] **Step 3: Implement**

```python
# report.py
    def only(self, rule_ids: set[str]) -> Report:
        return Report(reports=tuple(r for r in self.reports if r.rule_id in rule_ids))
```

Add `header: str | None = None` to `format_text` and, when set, emit it as the first line
followed by a blank line.

```python
# cli.py — in _build_parser, on the check subparser
    check.add_argument("--core", action="store_true", help="run only the core rule set")
```

```python
# cli.py — _run_check signature becomes (path: str, core: bool = False)
    report = Report.collect(layout, catalog, all_checks())
    header = None
    if core:
        core_ids = {r.id for r in catalog.core()}
        report = report.only(core_ids)
        header = f"core rules only ({len(core_ids)})"
    report = report.with_waivers(waivers)
    print(report.format_text(catalog, header=header))
    return report.exit_code(catalog)
```

and in `main`: `return _run_check(args.path, core=args.core)`.

- [ ] **Step 4: Run to verify green and commit**

Run: `uv run pytest && uv run ruff check . && uv run mypy`

```bash
git add src/arch_standard/report.py src/arch_standard/cli.py tests
git commit -m "feat: arch-standard check --core runs only the core rule set"
```

---

## Task 10: Migrate the legacy fixtures and delete the single-level accessors

**Files:**
- Modify: `tests/fixtures/good_project/**`, `tests/fixtures/bad_project/**`, `tests/fixtures/minimal_project/**`
- Modify: `src/arch_standard/checks/base.py`, `import_contracts.py`, `banned_symbols.py`, `ast_rules.py`, `schemas.py`
- Modify: every test that references the old paths

**Interfaces:**
- Produces: `ProjectLayout` loses `domain_dir(context)`, `application_dir(context)`, `infrastructure_dir(context)`. `entrypoints_dir(context)` stays (entrypoints remain context-level). All checks read only module-scoped paths. `_is_context` loses its legacy `_has_layer(p)` branch.

- [ ] **Step 1: Restructure `good_project`**

Move `src/sales/domain/model/*` → `src/sales/orders/domain/model/*`, renaming `aggregates.py` → `order.py`. Move `src/sales/application/order_service.py` → `src/sales/orders/application/order_service.py`. Move `src/sales/infrastructure/*` → `src/sales/orders/infrastructure/*`. Add `__init__.py` at every new level. Add `src/sales/shared/ids.py` with `OrderId` and repoint `Order`'s id field at it. Keep `src/sales/entrypoints/` where it is. Fix every intra-fixture import so `cd tests/fixtures/good_project/src && python -c "import sales.orders.application.order_service, sales.entrypoints.http"` succeeds.

- [ ] **Step 2: Restructure `bad_project` and `minimal_project`**

`bad_project`: same move into `src/sales/orders/`, keeping every deliberate violation
(`order.py` importing infrastructure, non-frozen `events.py`, unfrozen `value_objects.py`,
public mutable collection, oversized `order_service.py`, `clock_user.py`, `orm_leak.py`,
`noisy.py`). Add `src/sales/application/` as a directory containing an `__init__.py` so
ARCH-048 has something to fail on.
`minimal_project`: move `src/sales/domain/model/` → `src/sales/orders/domain/model/`.

- [ ] **Step 3: Delete the legacy accessors and legacy branches**

Remove `domain_dir`, `application_dir`, `infrastructure_dir` from `ProjectLayout`; remove the
`_has_layer(p) or` term from `_is_context`; remove the legacy fallbacks added in Tasks 4 and 6
(`_domain_files`' `project.domain_dir(context)` line, and `build_contracts`' single-level
contract branch). Repoint `schemas.py` at `project.src / context` for its
`integration_events.py` lookup.

- [ ] **Step 4: Update every test that referenced the old shape**

Run `uv run pytest` and fix each failure by pointing the assertion at the new path.
Remove any `xfail` markers added in Task 5. Do **not** weaken an assertion to make it pass —
if `bad_project` no longer trips a rule, the fixture lost its violation in the move; restore it.

- [ ] **Step 5: Verify the full matrix**

Run:
```bash
uv run pytest && uv run ruff check . && uv run ruff format --check . && uv run mypy
uv run arch-standard check tests/fixtures/good_project      # expect exit 0
uv run arch-standard check tests/fixtures/modular_project   # expect exit 0
uv run arch-standard check tests/fixtures/bad_project       # expect exit 1
uv run arch-standard check tests/fixtures/modular_project --core
```
Expected: all green; `bad_project` fails on MUST rules including ARCH-048 and ARCH-053.

- [ ] **Step 6: Commit**

```bash
git add tests/fixtures src/arch_standard tests
git commit -m "refactor: migrate fixtures to aggregate modules and drop single-level accessors"
```

---

## Task 11: Sync the prose partials and regenerate the standard

**Files:**
- Modify: `docs/standard/02-structure.md`, `03-bounded-contexts.md`, `05-domain.md`, `06-application.md`, `08-commons-shared-kernel.md`, `09-dependency-rules.md`, `15-progressive-structure.md`, `00-purpose.md`
- Modify: `src/arch_standard/docgen.py`
- Modify: `ARCHITECTURE_STANDARD.md` (regenerated)
- Test: `tests/test_docgen.py`, `tests/test_self.py`

**Interfaces:**
- Produces: `docgen._catalog_markdown` emits a **core table first** (`### Core rules`, the 12, in ID order) before the per-category tables, and each rule's expanded block gains a `**Tier:**` field on the Level/Automation line.

- [ ] **Step 1: Update the prose partials from the spec**

Transcribe the rewritten spec sections, dropping first-person and meta-process language as in the original partials:
- `02-structure.md` ← spec §2.1–2.5 (new tree, the two levels, what-goes-where, no context application, the Read/Query layer)
- `03-bounded-contexts.md` ← §3.1–3.7 (adds cross-aggregate flow and the declared context graph)
- `05-domain.md` ← §5.1–5.5 (projections vs the read layer)
- `06-application.md` ← §6.1–6.5 (one service per aggregate module; integration events conditional)
- `08-commons-shared-kernel.md` ← §8.1–8.2 (`arch-commons` as a versioned package)
- `15-progressive-structure.md` ← §15 (thresholds now point at the model)
- `00-purpose.md` ← §0 framing table (the six new rows)
- `09-dependency-rules.md` — add one sentence introducing the core tier above the `<!-- RULES_CATALOG -->` marker; the marker stays the only generated content.

- [ ] **Step 2: Write the failing test**

```python
# append to tests/test_docgen.py
def test_given_the_catalog__when_rendered__then_the_core_table_comes_first() -> None:
    text = render_standard(Catalog.load(RULES), PROSE)
    assert "### Core rules" in text
    assert text.index("### Core rules") < text.index("### dependencies")
    for rid in ("ARCH-046", "ARCH-050", "ARCH-051", "ARCH-052", "ARCH-053"):
        assert rid in text


def test_given_a_rule_block__when_rendered__then_the_tier_is_shown() -> None:
    text = render_standard(Catalog.load(RULES), PROSE)
    assert "**Tier:**" in text
```

- [ ] **Step 3: Run to verify it fails**

Run: `uv run pytest tests/test_docgen.py -k "core_table or tier" -v`
Expected: FAIL — `"### Core rules" not in text`.

- [ ] **Step 4: Implement the docgen change**

```python
# docgen.py — inside _catalog_markdown, before the per-category loop
    out.append("### Core rules")
    out.append("")
    out.append("Binding from day one. `arch-standard check --core` runs exactly these.")
    out.append("")
    out.append("| ID | Rule | Level | Automation |")
    out.append("|---|---|---|---|")
    for r in catalog.core():
        out.append(f"| {r.id} | {r.name} | {r.level.value} | {r.automation.value} |")
    out.append("")
```

and in `_rule_block`, extend the metadata line:

```python
        f"- **Level:** {rule.level.value} · **Automation:** {rule.automation.value} "
        f"· **Tier:** {rule.tier.value} · **Category:** {rule.category}",
```

- [ ] **Step 5: Regenerate and verify**

Run:
```bash
uv run arch-standard docs
uv run pytest && uv run ruff check . && uv run ruff format --check . && uv run mypy
uv run arch-standard docs --check
```
Expected: all green; `docs --check` exits 0. Open `ARCHITECTURE_STANDARD.md` and confirm the core table renders before the category tables and every new rule appears.

- [ ] **Step 6: Commit**

```bash
git add docs/standard ARCHITECTURE_STANDARD.md src/arch_standard/docgen.py tests
git commit -m "docs: sync partials with the restructured standard and lead with the core tier"
```

---

## Self-Review

**1. Spec coverage.** §2.1 tree → Tasks 1, 2, 10. §2.2 two levels → Tasks 1, 3 (ARCH-046, 049). §2.3 what-goes-where → Task 11 prose. §2.4 no context application → Task 7 (ARCH-048). §2.5 read layer → Tasks 3, 6 (ARCH-052), 7 (ARCH-051). §3.6 cross-aggregate flow → prose only (Task 11); it is a review rule with no automatable form, consistent with its `manual` peers. §3.7 context graph → Task 8 (ARCH-050). §5.5 projections vs read → Tasks 7, 11. §8.1 `arch-commons` → prose only (Task 11); the packaging itself is Plan 3. §9 tiers → Tasks 3, 9, 11. §15 thresholds → Task 5 (`_check_promotion_thresholds`), Task 11 prose. §16.3 versioning → **not in this plan** (Plan 3), stated in the header.

**2. Placeholder scan.** No TBD/TODO steps. Task 2 and Task 10 are fixture-construction tasks with explicit file lists, exact contents for the load-bearing files, and an importability gate (Task 2 Step 4, Task 10 Step 5) that fails loudly if the tree is wrong. Task 11's prose is transcription with a section→source mapping, gated by the docgen tests.

**3. Type consistency.** `ProjectLayout.modules(context) -> tuple[str,...]`, `.iter_modules() -> Iterator[tuple[str,str]]`, `.module_domain_dir/module_application_dir/module_infrastructure_dir(context, module) -> Path`, `.shared_dir(context) -> Path`, `.read_dir(context) -> Path` — used identically in Tasks 4, 5, 6, 7. `outcome_for(level, has_findings) -> Outcome` (existing) used by Tasks 4, 7, 8. `Finding(rule_id, path, line, message)` and `CheckReport(rule_id, outcome, findings)` unchanged. `Tier` and `Catalog.core()` defined in Task 3, consumed in Tasks 9 and 11. `Report.only(set[str]) -> Report` and `format_text(catalog, header=None)` defined and consumed in Task 9. `StructureCheck` / `ContextGraphCheck` both expose `rule_ids: tuple[str, ...]` and `run(project, catalog)`, matching the `Check` Protocol.

---

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-09-06-validator-aggregate-modules.md`. Two execution options:

**1. Subagent-Driven (recommended)** — a fresh subagent per task, review between tasks, fast iteration.

**2. Inline Execution** — tasks executed in this session via executing-plans, batch execution with checkpoints.

Which approach?
