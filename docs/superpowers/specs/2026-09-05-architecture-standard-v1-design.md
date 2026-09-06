# Architecture Standard v1 — Design Spec

- **Status:** Draft for review
- **Date:** 2026-09-05
- **Owner:** David Rodriguez
- **Repo role:** This repository is the canonical source of the Architecture Standard.
- **Scope of this document:** the *design* of the standard. It is the input to a later
  implementation plan that produces `ARCHITECTURE_STANDARD.md`, the machine-readable
  rule catalog, the validator, the project template, and the Superpowers skill.
  It does **not** itself ship any of those artifacts.

---

## 0. Framing decisions (locked)

| Topic | Decision |
|---|---|
| Language ecosystem | **Python first.** Principles are written language-agnostic; concrete tooling and examples are Python (import-linter, grimp, ruff, pytest, tach). |
| Deployment topology | **Modular monolith** by default. Bounded-context boundaries and contracts are defined *as if the contexts were separable*; physically it stays one deployable. |
| Naming language | **English** for all identifiers, folders, rule IDs, and for `ARCHITECTURE_STANDARD.md`. |
| Session deliverable | This design spec + the outline of `ARCHITECTURE_STANDARD.md`. |
| Ports | `typing.Protocol` (structural typing; adapters do not inherit). |
| Error handling | Exceptions are the standard mechanism. `DomainError` for expected business errors. No `Result`/`Either` type in the core. |
| Runtime model | **Synchronous.** Ports, repositories, Unit of Work, and handlers are `def`, not `async def`. |
| Identifier generation | **Application-generated** (`next_identity()`, UUIDv7). Repositories receive aggregates whose identity is already assigned. |
| Input validation | Pydantic at the edge (entrypoints) only. Business invariants in the domain. Commands are frozen dataclasses. Pydantic MUST NOT appear in `domain/` or `application/`. |
| Event publication | Transactional outbox is **mandatory** when delivery / transactional side-effect guarantees are required; optional otherwise. |
| Read models | Domain-derived projections live in `domain/model/projections.py`. Query/dashboard/presentation read models live outside the domain, introduced when complexity justifies it. |
| Mapping | Manual mapping for domain-facing boundaries. Libraries allowed for mechanical mapping at infrastructure/transport boundaries. |
| Cross-context communication | Synchronous by default, contract-mediated, wired in `bootstrap/`, zero imports between contexts. Asynchronous integration events when the use case explicitly tolerates eventual consistency. |
| Process wiring | `main.py` is the process entrypoint. `bootstrap/` is the Composition Root. |

---

## 1. Philosophy

**Organize code by business first, then apply Clean/Hexagonal inside each business
capability.** The top architectural level represents business boundaries (bounded
contexts), never technology (`controllers/`, `services/`, `repositories/`).

Three load-bearing ideas:

1. **The Dependency Rule.** Source-code dependencies point inward:
   `entrypoints → application → domain` and `infrastructure → domain/application`.
   The domain depends on nothing. Infrastructure is plugged in, never imported by the core.

2. **Business-capability cohesion at the top.** A change to "how orders work" touches
   one context. A change to "how we talk to Postgres" touches one adapter module.

3. **Progressive Structure.** Structure grows when it hurts, not before. A context starts
   with flat modules (`domain/model.py`, `application/<capability>.py`,
   `infrastructure/<adapter>.py`). It is promoted to packages only past defined
   thresholds (Section 15). The standard defines the thresholds; it does not mandate the
   maximal structure from day one.

The standard is **rule-based, deterministic, and verifiable** so that it is consumable
by humans, by Claude Code, by an architecture-reviewer agent, and by CI.

---

## 2. Project structure

### 2.1 Canonical tree

```text
project/
├── main.py                        # process entrypoint: starts the app, calls bootstrap/
├── pyproject.toml
├── .importlinter                  # dependency contracts
├── src/
│   ├── <context>/                 # one bounded context
│   │   ├── entrypoints/
│   │   │   ├── http.py            # inbound adapter: HTTP/GraphQL
│   │   │   ├── events.py          # inbound adapter: message/event consumers
│   │   │   ├── cli.py             # inbound adapter: CLI
│   │   │   ├── cron.py            # inbound adapter: scheduled jobs
│   │   │   └── providers.py       # thin: pulls wired services from the container
│   │   ├── domain/
│   │   │   ├── model/
│   │   │   │   ├── aggregates.py  # (or entities.py + aggregates.py once it grows)
│   │   │   │   ├── value_objects.py
│   │   │   │   ├── events.py      # domain events (frozen, past tense)
│   │   │   │   ├── ports.py       # ALL domain ports (Protocol): repositories, UoW,
│   │   │   │   │                  #   EventBus, Clock, IdGenerator, domain-needed gateways
│   │   │   │   ├── projections.py # domain-derived read projections (when they exist)
│   │   │   │   └── exceptions.py  # concrete domain exceptions (subclass commons DomainError)
│   │   │   ├── services.py        # domain services (optional; only if needed)
│   │   │   └── specifications.py  # specifications / policies (optional)
│   │   ├── application/
│   │   │   ├── <capability>.py    # service class + its command objects + colocated Protocols
│   │   │   └── integration_events.py  # integration events this context publishes + mapping
│   │   └── infrastructure/
│   │       ├── <adapter>.py       # one module per outbound adapter
│   │       ├── <aggregate>_mapper.py  # data mapper aggregate <-> ORM model
│   │       └── unit_of_work.py    # context UoW implementation
│   ├── commons/
│   │   ├── types/                 # dependency-free technical primitives. Importable by ALL
│   │   │   ├── ids.py
│   │   │   ├── pagination.py
│   │   │   ├── errors.py          # DomainError, ApplicationError base classes
│   │   │   ├── clock.py           # Clock Protocol
│   │   │   └── unit_of_work.py    # AbstractUnitOfWork Protocol (transaction semantics only)
│   │   └── infrastructure/        # shared framework-bound technical implementations
│   │       ├── sqlalchemy_uow.py  # SqlAlchemyUnitOfWork base
│   │       ├── in_memory_uow.py   # InMemoryUnitOfWork fake (no DB) for tests
│   │       ├── sql_repository.py  # optional SQL repository base
│   │       └── outbox.py          # transactional outbox machinery
│   ├── shared_kernel/             # governed shared domain concepts (policy-bearing VOs).
│   │                              #   NOT scaffolded until genuinely needed.
│   └── bootstrap/                 # Composition Root: config, singletons, DI container,
│                                  #   service/UoW factories, router registration,
│                                  #   consumer startup
└── tests/
```

### 2.2 What goes where

| You are adding... | It goes in... |
|---|---|
| A new business boundary | `src/<context>/` |
| A rule that protects an invariant across objects | an aggregate method in `<context>/domain/model/` |
| A calculation that spans aggregates | `<context>/domain/services.py` |
| A use case (state change) | a method on a service class in `<context>/application/<capability>.py` |
| A persistence/broker/third-party integration | one module in `<context>/infrastructure/` |
| A contract the domain needs | `<context>/domain/model/ports.py` |
| A non-domain outbound contract used by one use case | a `Protocol` colocated in that `application/<capability>.py` |
| A fact other parts of the same context react to | a domain event in `<context>/domain/model/events.py` |
| A fact other contexts consume | an integration event in `<context>/application/integration_events.py` |
| A dependency-free technical primitive | `commons/types/` |
| A shared framework-bound technical implementation | `commons/infrastructure/` |
| A domain concept genuinely shared by 2+ contexts, with business policy | `shared_kernel/` (with governance) |
| Wiring / config / DI | `bootstrap/` |

### 2.3 The optional `module` level

When a single context legitimately owns **two or more separable sub-areas** each with
its own aggregates, insert a module level:
`src/<context>/<module>/{domain,application,infrastructure}/`. Off by default.

---

## 3. Bounded contexts

### 3.1 Rules

- The first level of `src/` is bounded contexts. Each context owns its own model,
  language, and rules.
- **A context MUST NOT import another context's internals** (`domain/`, `application/`,
  `infrastructure/`). Zero imports between contexts. (ARCH-012)
- Contracts (ports, event schemas, boundary DTOs) are defined *as if the contexts were
  physically separable*. (ARCH — "separable contracts")
- No dependency cycles between contexts. (ARCH-013)

### 3.2 Communication — decision order

| Situation | Mechanism |
|---|---|
| Consumer needs data/decision from another context **now**, and staleness is unacceptable | **Synchronous, contract-mediated.** Consumer declares its own consumer-driven port; `bootstrap/` wires an adapter backed by the other context's application service; consumer's `infrastructure/<x>_gateway.py` implements the port and does the ACL. Zero imports between contexts. |
| The use case explicitly tolerates eventual consistency; or fan-out to many consumers; or crossing a future service boundary | **Asynchronous integration events.** Producer publishes a versioned, serialized event; each consumer has an ACL translating the raw message to its own model. Published via transactional outbox when delivery must be guaranteed. |
| Producer needs a consumer to *do something* | Send a **command**, not an event. Events are facts (past tense); they never oblige a handler. |
| A concept looks shared but means different things in each context | **Duplicate.** Each context models its own. Sharing is the exception. |

### 3.3 Anti-Corruption Layer

Every inbound translation from another context (sync response or async message) passes
through an ACL in the consumer's `infrastructure/`. The ACL is the only place that knows
the other context's contract shape; the rest of the consumer sees only its own model.

### 3.4 Published Language

The vocabulary of integration events is a shared contract expressed as **schema**
(JSON Schema / Avro / Pydantic export) in an events catalog — never as importable
classes. Every integration event has a published, versioned schema. (ARCH-024, ARCH-044)

### 3.5 Extraction path

Because infrastructure is behind ports and cross-context contracts are already explicit,
extracting a context to its own service means: replace the in-process gateway adapter
with an HTTP client, replace the in-process bus with a real broker. `domain/` and
`application/` are untouched.

---

## 4. Entry points

### 4.1 Flow

```text
External stimulus → Entrypoint → Application use case → Domain
```

### 4.2 Rules

- Entrypoints are **inbound adapters**: HTTP, GraphQL, Kafka/RabbitMQ/SQS consumers,
  CLI, cron.
- An entrypoint **translates** a stimulus into a command/query, calls **one** application
  service method, and maps the result/exception back to the transport (status codes,
  serialization). (ARCH-004-family)
- An entrypoint obtains a **fully wired service** from `<context>/entrypoints/providers.py`
  (which pulls from the `bootstrap/` container). It **MUST NOT construct infrastructure
  adapters** itself. (ARCH-009)
- An entrypoint **MUST NOT** call persistence/adapters/DB directly
  (`repo.save(...)`, `session.execute(...)`, `http_client.get(...)`). The only thing it
  calls is the application service. (ARCH-009)
- An entrypoint **MUST NOT** contain business logic. (ARCH-010, SHOULD)
- An entrypoint **MUST NOT** call another entrypoint. (ARCH-011)
- An entrypoint **MAY** import `domain/model/exceptions.py` (and the `commons` base
  errors) solely to map domain exceptions to transport responses.
- Pydantic request/response models live **only** in entrypoints. (ARCH — pydantic edge)

### 4.3 Exceptions to the rule

- Health/readiness endpoints MAY read infrastructure state directly (they are not
  business use cases).
- A pure pass-through admin/debug endpoint MAY be exempt if explicitly marked and
  excluded from the public surface — discouraged, requires justification.

---

## 5. Domain layer

### 5.1 Contents and dependencies

`domain/` contains: `model/` (aggregates, entities, value objects, domain events,
ports, projections, exceptions), `services.py`, `specifications.py`.

`domain/` depends on: the standard library + `commons/types/` + (rarely) `shared_kernel/`.
Nothing else. No frameworks, no I/O, no ORM, no `datetime.now()` / `uuid4()` directly
(use `Clock` / `IdGenerator` ports), no application DTOs. (ARCH-001..004)

### 5.2 Preference order

Start with a method on the aggregate. Extract to a domain service when logic spans
aggregates. Extract to a Policy / Specification / Factory **only** with demonstrated
variation or reuse.

### 5.3 Tactical patterns — when to use, when not

**Value Object** — use for a concept described by its values (`Money`, `Email`,
`DateRange`, `Quantity`), no lifecycle, needs centralized validation and value equality.
Do not use when it needs identity over time (→ Entity), or when it is a bare primitive
with no invariants (avoid "wrapper obsession"). `@dataclass(frozen=True)`, validate in
`__post_init__`, no setters, methods return new instances. (ARCH-031)

**Entity** — use when the concept has a stable identifying ID even as attributes change,
and its history matters. Do not use when it is interchangeable by value (→ VO) or exists
only inside another entity and is never referenced from outside. Identity by ID, mutation
only via business-named methods, no setters enabling invalid state. (ARCH-018)

**Aggregate + Aggregate Root** — use when invariants span several objects and must always
hold. Do not lump unrelated objects together. Access/mutate **only via the root**
(ARCH-019); reference other aggregates **by ID** (ARCH-020); one transaction modifies
**one aggregate** (ARCH-021, MUST with documented justification); validate invariants on
every mutation. *God Aggregate* smell: >~7 invariants or hundreds of loaded children.

**Domain Service** — use when logic involves **multiple aggregates** and belongs to none,
or needs a domain port. Do not use when the logic fits on an aggregate (→ anemic domain),
when it is orchestration (→ application service), or a pure calculation over one aggregate
(→ aggregate method). Stateless, takes aggregates/VOs as parameters, I/O only via
`domain/model/ports.py`, knows nothing about transactions or DTOs.

**Domain Event** — use when another part of the **same context** reacts to a state change
in a decoupled way, or the fact must be recorded to derive integration events. Do not use
when the reaction is part of the same invariant and transaction, or when it is
cross-context communication (→ integration event). `frozen`, past tense, no side-effects,
carries `occurred_at` + needed IDs. Dispatched **after** persistence. (ARCH-023)

**Repository (abstraction)** — use when an aggregate root needs persistence and retrieval
by identity or specification. Do not use for complex multi-aggregate read queries
(→ read model); do not add `find_x_with_y() -> DTO` (*Repository as business service*).
Interface in `domain/model/ports.py`, methods at root level (`get`, `add`, `save`,
`next_identity`), returns aggregates not rows/DTOs. (ARCH-022)

**Factory** — use when building a valid aggregate needs non-trivial logic, or
reconstruction from persistence differs from fresh creation. Do not add a factory that
only wraps the constructor. Prefer a `@classmethod` on the aggregate (`Order.place(...)`)
unless the logic is large or needs a port.

**Specification** — use when the same selection/validation rule is used in 2+ places, or
rules combine dynamically. Do not use for one-off rules (`order.is_cancellable()`) or
purely to filter in the DB. Stateless, `is_satisfied_by(candidate) -> bool`.

**Policy** — use when there are **multiple real strategies** for a decision chosen at
runtime. Do not use for a single rule, or when "policy" actually means
authorization/rate-limiting (that is application/infra). Interface + implementations in
`domain/`.

### 5.4 Exceptions

Concrete domain exceptions live in `domain/model/exceptions.py`, subclassing
`commons.types.errors.DomainError`. The domain never raises library exceptions.
(ARCH-032) `DomainError` also covers **expected** business errors (validation,
precondition failures) — there is no `Result` type.

### 5.5 Projections

Domain-derived projections (a read shape computed from the model, still expressed in
domain terms) live in `domain/model/projections.py`. Query/dashboard/presentation read
models are **not** domain — they live outside, introduced when their complexity justifies
a dedicated read path (Section 15).

---

## 6. Application layer

### 6.1 Responsibility

Coordinate use cases: load an aggregate, invoke its business method, persist via the Unit
of Work, publish integration events, map domain ↔ DTO, control the transaction boundary,
enforce use-case-level authorization. **No business invariants** — those are in the
domain. (ARCH-005..007, ARCH-027, ARCH-029)

### 6.2 Shape

**One application service class per capability (usually per aggregate); one public method
per use case.** (ARCH-030, SHOULD)

```python
# application/order_placement.py
@dataclass(frozen=True)
class CreateOrder:
    customer_id: str
    lines: tuple[OrderLineInput, ...]

class OrderNotifier(Protocol):           # colocated non-domain outbound contract
    def order_placed(self, order_id: OrderId) -> None: ...

class OrderPlacementService:
    def __init__(
        self, uow: SalesUnitOfWork, bus: EventBus, notifier: OrderNotifier
    ) -> None: ...

    def create_order(self, command: CreateOrder) -> OrderId:
        with self._uow:
            order = Order.place(CustomerId(command.customer_id), command.lines)
            self._uow.orders.add(order)
            self._uow.commit()
        self._bus.publish_all(self._uow.collect_new_events())
        return order.id
```

Guardrails (ARCH-030):
- One method = one use case = one transaction.
- Zero business rules in the service. An `if` about business meaning → move to the domain.
- Separate read from write into different service classes when reads grow.
- Split the class past ~5–7 methods, **or** when constructor dependencies stop being
  cohesive (a method needs something the others do not).
- Name by capability (`OrderPlacementService`), never a `OrderService` catch-all.
- Command objects are frozen dataclasses; they may live in the same module as the service.

### 6.3 Ports

There is **no** `application/ports.py`. All contracts with a stable shape
(`OrderRepository`, `SalesUnitOfWork`, `EventBus`, `Clock`, `IdGenerator`) live in
`domain/model/ports.py`. A peripheral outbound contract used by exactly one use case is a
**`Protocol` colocated** in that use case's module. (ARCH-042, SHOULD)

### 6.4 Integration events

`application/integration_events.py` defines the integration events this context
**publishes** (its outbound contract) and the mapping domain events → integration events
→ `EventBus`. Consumers never import this module; they see serialized messages only.
(ARCH-024)

### 6.5 Domain logic vs application orchestration

| Domain logic | Application orchestration |
|---|---|
| "An order cannot exceed the customer's credit limit" | "Load the order, add the item, save, publish `ItemAdded`" |
| "A shipped order cannot be cancelled" | "Begin transaction, on failure roll back and publish nothing" |
| "Discount = policy applied to line totals" | "Map the HTTP body to a command; map the aggregate to a response DTO" |

---

## 7. Infrastructure layer

### 7.1 Rules

- **One module per outbound adapter.** No sub-folders by type. Sub-folder only when a
  context accumulates many adapters of one kind (exception, not norm).
- Adapters **implement** ports declared in `domain/model/ports.py`; the core imports
  abstractions only. (ARCH-008)
- **No Active Record.** The aggregate does not know its persistence. A
  `<aggregate>_mapper.py` translates aggregate ↔ ORM model. (ARCH-028)
- Adapters contain **no business logic** and make **no orchestration decisions**.
- `infrastructure/` MAY import `commons/infrastructure/`; `domain/` and `application/`
  MUST NOT. (ARCH-034)

### 7.2 Unit of Work

Three responsibilities, no more:
1. **Transaction boundary** — `__enter__` / `__exit__` (auto-rollback if `commit()` was
   not called), `commit()`.
2. **Repository aggregation point** for one context — all its repositories share the same
   session/transaction.
3. **Domain event collection** — `collect_new_events()` drains events from the aggregates
   the repositories loaded/added.

```python
# commons/types/unit_of_work.py
class AbstractUnitOfWork(Protocol):
    def __enter__(self) -> "AbstractUnitOfWork": ...
    def __exit__(self, *exc: object) -> None: ...
    def commit(self) -> None: ...
    def collect_new_events(self) -> Iterable[DomainEvent]: ...
```

```python
# sales/domain/model/ports.py
class SalesUnitOfWork(AbstractUnitOfWork, Protocol):
    orders: OrderRepository
```

- Context UoW interface: `<context>/domain/model/ports.py`.
- Real implementation: `<context>/infrastructure/unit_of_work.py`
  (`SqlAlchemySalesUnitOfWork(SqlAlchemyUnitOfWork)`).
- Test fake: `commons/infrastructure/in_memory_uow.py` provides the generic in-memory
  transaction fake; the context's test helper composes it with in-memory repositories.
- Every use-case write goes through a UoW; the service never commits repositories
  individually. (ARCH-033)

### 7.3 Transactional outbox

- **Mandatory** when event publication or a transactional side-effect requires a
  delivery / consistency guarantee: integration events are written to an `outbox` table
  **in the same transaction**; a separate process publishes them. (ARCH-036)
- **Optional** (`publish-after-commit`) when no such guarantee is required.
- Machinery lives in `commons/infrastructure/outbox.py`.

---

## 8. `commons/` and `shared_kernel/`

### 8.1 Two technical tiers

| | `commons/types/` | `commons/infrastructure/` |
|---|---|---|
| Content | dependency-free technical primitives, protocols | framework-bound shared technical implementations |
| Examples | `Result`-free error bases, `EntityId`, `Pagination`, `Clock` Protocol, `AbstractUnitOfWork` | `SqlAlchemyUnitOfWork`, `InMemoryUnitOfWork`, SQL repository base, outbox machinery |
| Importable by | everyone, including `domain/` | only `infrastructure/`, `entrypoints/`, `bootstrap/`, tests |
| Forbidden | any business meaning, any framework import | — |

Rules: ARCH-015 (`commons.types` ⊥ contexts/application/infrastructure/shared_kernel),
ARCH-016 (`commons.types` no business logic), ARCH-034 (`commons.infrastructure` ⊥
domain/application), ARCH-035 (`commons.types` ⊥ frameworks).

### 8.2 `shared_kernel/`

Deliberately shared **domain** concepts across 2+ contexts, with sign-off from every
consuming context. **Only small, immutable, policy-bearing value objects** — no entities,
aggregates, domain services, or repositories.

**The test:** does the concept encode a business policy?
- **No** (typed wrapper + format validation, e.g. `Email` syntax, `Money` arithmetic that
  raises on currency mismatch) → `commons/types/`. No ceremony.
- **Yes** (accounting rounding, tax rules, business-specific validation, an ID two
  contexts agree to share) → `shared_kernel/` with change governance.

Governance: a change requires review from every consuming context; the kernel is
versioned. **Not scaffolded until the first genuine shared policy-bearing concept exists.**
(ARCH-014: `shared_kernel` ⊥ all contexts.)

Generic subdomains (notifications, identity) are **other bounded contexts**, not shared
code — consumed via the Section 3 mechanisms.

---

## 9. Dependency rules — catalog

Every rule in `ARCHITECTURE_STANDARD.md` carries the full schema:
`ID · name · description · rationale · correct example · incorrect example · level
(MUST/SHOULD/MAY) · automation (full/partial/manual)`.

The machine-readable source of truth is `rules/*.yaml`; the Markdown is generated from it.

### 9.1 Dependencies & layering

| ID | Rule | Level | Automation |
|---|---|---|---|
| ARCH-001 | `domain/` does not depend on `infrastructure/` | MUST | full |
| ARCH-002 | `domain/` does not depend on `application/` | MUST | full |
| ARCH-003 | `domain/` does not depend on frameworks (web, ORM, DI, pydantic) | MUST | full |
| ARCH-004 | `domain/` performs no I/O (clock, random, network, disk) | MUST | partial |
| ARCH-005 | `application/` does not depend on `infrastructure/` | MUST | full |
| ARCH-006 | `application/` does not depend on `entrypoints/` | MUST | full |
| ARCH-007 | `application/` does not construct concrete adapters | MUST | full |
| ARCH-008 | Infrastructure implements ports; the core imports abstractions only | MUST | full |
| ARCH-009 | Entrypoints obtain wired services from providers; never construct or call infrastructure directly | MUST | partial |
| ARCH-010 | Entrypoints contain no business logic | SHOULD | partial |
| ARCH-011 | Entrypoints call application services, not other entrypoints | MUST | full |
| ARCH-012 | A context imports nothing from another context | MUST | full |
| ARCH-013 | No dependency cycles between contexts | SHOULD | full |
| ARCH-014 | `shared_kernel/` imports nothing from any context | MUST | full |
| ARCH-015 | `commons/types/` imports nothing from contexts/application/infrastructure/shared_kernel | MUST | full |
| ARCH-016 | `commons/types/` contains no business logic | MUST | manual |
| ARCH-017 | Nothing imports `bootstrap/` | MUST | full |
| ARCH-034 | `commons/infrastructure/` is not imported by `domain/` or `application/` | MUST | full |
| ARCH-035 | `commons/types/` does not import any framework | MUST | full |
| ARCH-037 | Entrypoint wiring is defined in per-context `providers.py`, backed by `bootstrap/` | MUST | partial |

### 9.2 Model integrity (DDD)

| ID | Rule | Level | Automation |
|---|---|---|---|
| ARCH-018 | No setters that permit invalid aggregate/entity state | SHOULD | partial |
| ARCH-019 | Internal aggregate collections are not exposed mutable | SHOULD | partial |
| ARCH-020 | Inter-aggregate references are by ID, not object | SHOULD | partial |
| ARCH-021 | One transaction modifies one aggregate (UoW boundary) | MUST* (justified) | partial |
| ARCH-022 | Repositories operate at root level and return aggregates, not rows/DTOs | MUST | partial |
| ARCH-023 | Domain events are immutable and past-tense | MUST | full |
| ARCH-028 | No Active Record: the aggregate does not know its persistence | MUST | partial |
| ARCH-031 | Value Objects are immutable and validate on construction | MUST | partial |
| ARCH-032 | The domain raises only exceptions derived from `commons` `DomainError` | SHOULD | partial |
| ARCH-033 | Every use-case write goes through a Unit of Work | MUST | partial |

### 9.3 Application

| ID | Rule | Level | Automation |
|---|---|---|---|
| ARCH-024 | Integration events have a versioned schema and live in `application/integration_events.py` | MUST | partial |
| ARCH-025 | Cross-context communication is through a declared contract, never imports; synchronous by default (composition-root-mediated), asynchronous when the use case tolerates eventual consistency | MUST | full |
| ARCH-026 | External-provider dependencies sit behind a port | SHOULD | partial |
| ARCH-027 | The domain does not cross the application boundary (mapped to DTO) | SHOULD | manual |
| ARCH-029 | Use cases express intent, not generic CRUD | SHOULD | manual |
| ARCH-030 | One application service class per capability; one method per use case; ≤ ~7 methods | SHOULD | partial |
| ARCH-036 | Integration events are published via transactional outbox when a delivery/consistency guarantee is required | MUST* (conditional) | manual |
| ARCH-042 | Non-domain outbound contracts are colocated `Protocol`s, not in `domain/model/ports.py` | SHOULD | manual |
| ARCH-045 | A context depends only on consumer-driven contracts it declares for what it needs from another context | MUST | partial |

### 9.4 Testing

| ID | Rule | Level | Automation |
|---|---|---|---|
| ARCH-038 | Domain objects are never mocked | SHOULD | partial |
| ARCH-039 | In-memory fakes share the contract test with the real adapter | SHOULD | manual |
| ARCH-040 | Test names follow `given_<state>__when_<action>__then_<result>` | SHOULD | full |

### 9.5 Cross-cutting

| ID | Rule | Level | Automation |
|---|---|---|---|
| ARCH-043 | Cross-context flows carry a correlation ID in the event/message envelope | MUST | partial |
| ARCH-044 | Every integration event has a published schema in the events catalog | MUST | partial |

### 9.6 Progressive structure

| ID | Rule | Level | Automation |
|---|---|---|---|
| ARCH-041 | A module is promoted to a package only past the Section 15 thresholds | MAY (guidance) | partial |

---

## 10. DDD rules — decision trees

`ARCHITECTURE_STANDARD.md` renders Section 5.3 as explicit decision trees, e.g.:

```text
Adding behavior?
├── Does it protect an invariant of ONE aggregate?        → method on the aggregate
├── Does it span MULTIPLE aggregates?                      → domain service
├── Is it choosing between MULTIPLE runtime strategies?    → policy
├── Is it a reusable predicate used in 2+ places?          → specification
├── Is it multi-step coordination + persistence + events?  → application service method
└── Is it translating a stimulus or a response?            → entrypoint / mapper
```

---

## 11. Testing strategy

### 11.1 Pyramid

| Level | Tests | Dependencies | Speed |
|---|---|---|---|
| Domain | aggregates, VOs, services, specs, policies — invariants and rules | none, real objects | µs |
| Application | service methods (use cases) — orchestration, transaction, events published | real domain + in-memory fakes of the ports | ms |
| Adapter / integration | each adapter against its real technology | real DB/broker (testcontainers) | s |
| Contract | integration event schema, producer ↔ consumers | schema fixtures | ms |
| End-to-end | full flow through a real entrypoint | context stack | s+ |

### 11.2 Naming

`given_<state>__when_<action>__then_<result>` — double underscore separates the three
parts. Example:
`given_shipped_order__when_add_item__then_raises_order_already_shipped`. (ARCH-040)

### 11.3 Mock / don't mock

- **Never mock:** domain objects (aggregates, VOs, services), the code under test,
  `shared_kernel` VOs. (ARCH-038)
- **Use in-memory fakes, not mocks:** repositories (`InMemoryOrderRepository` over a
  dict), `EventBus` (`RecordingEventBus`), `Clock` (`FixedClock`). The same contract test
  runs against the fake and the real adapter — the fake cannot lie. (ARCH-039)
- **Mock only in adapter tests:** the third party's SDK when testing your adapter — and
  even then prefer a fake server / VCR / testcontainer.
- **Rule of thumb:** an application test with more than 1–2 mocks means the service does
  too much or dependencies are not properly injected.

### 11.4 Per-layer guidance

- **Aggregates:** pure objects, never through the repository. Assert new state, emitted
  domain events, and that invalid cases raise the correct domain exception. One test per
  rule, not per method.
- **Application services:** real domain + fakes. Assert the right aggregate was loaded,
  the business method was called, persistence happened, the expected integration events
  were published, the transaction commits/rolls back. Do not re-test domain rules here.
  Test rollback explicitly.
- **Adapters:** repository round-trip (`add` → `get` → full equality) + specification →
  query translation; publisher/consumer against a real broker, serialized message matches
  the Published Language schema.
- **Contract tests:** producer — every emitted event validates against its published
  schema; consumer — inbound fixtures validate against the producer schema
  (consumer-driven: removing a field the consumer uses breaks the build). Schema change =
  new event version, never in-place edit.

### 11.5 Coverage as a rule

Domain > 90% (pure, cheap). Application: every use case with happy path + rollback +
events. Adapters: round-trip + error translation. E2E: critical business flows only.

---

## 12. Anti-patterns

| Anti-pattern | Why it is a problem | Alternative |
|---|---|---|
| Anemic Domain Model | logic scattered in services, invariants unprotected | behavior on the aggregate |
| God Aggregate | huge transactions, lock contention, not extractable | split by real consistency boundaries; reference by ID |
| God / Fat Application Service | logical cohesion, merge contention, test setup explosion | service per capability, ≤7 methods, split on incohesive deps |
| Fat Controller / Fat Entrypoint | untestable without transport, logic not reusable | entrypoint only translates + calls one service method |
| Business logic in adapters | hidden from domain tests, duplicated | adapters only translate; decisions in domain/application |
| Repository as business service | business queries leak into persistence, repo grows unbounded | repo = collection of roots; complex reads → read model |
| Domain imports infrastructure / frameworks | domain not testable in isolation, tech locked in | DIP — domain defines ports, infra implements |
| Active Record aggregate | invariants entangled with the DB, not unit-testable | data mapper; plain aggregate |
| Shared module as junk drawer | global coupling, contexts cannot evolve independently | strict `commons` / `shared_kernel` rules; duplicate by default |
| Cross-context coupling | contexts fused, not independently deployable | integration events + ACL; zero imports (ARCH-012) |
| Premature abstraction | indirection with no payoff, wrong abstraction locks in | YAGNI + Progressive Structure; abstract on 2+ concrete cases |
| Domain leaking across the application boundary | transport coupled to the internal model | use case returns a DTO; map in application |
| Setter-driven aggregates | illegal state transitions, invariants bypassed | intention-revealing methods that validate |
| CRUD use cases | no business intent, invariants unverifiable per change | intention-revealing use cases |
| Event as command | hidden coupling, a synchronous call in disguise | events are past-tense facts; send a command to make something happen |
| Mock-heavy tests | tests couple to implementation, refactors break tests | real domain + in-memory fakes; assert on state and events |

---

## 13. MUST / SHOULD / MAY

| Level | Meaning | On deviation |
|---|---|---|
| MUST | architectural invariant | build fails, no merge. Exception = documented ADR + standard maintainer approval |
| SHOULD | strong default | allowed with a one-line justification in the PR or an ADR; reviewer must acknowledge |
| MAY | genuine project choice | documented so it reads as sanctioned, not accidental |

`MUST*` = conditional MUST (applies when the stated condition holds; e.g. ARCH-021,
ARCH-036).

Exception process: an `docs/adr/NNNN-*.md` records the rule waived, the reason, the
scope, and an expiry/review date. The validator reads an allowlist generated from active
ADRs.

---

## 14. Architecture as Code

### 14.1 Tooling map (Python)

| Mechanism | Tool | Rules | Runs in |
|---|---|---|---|
| Import contracts (layering, independence, cycles) | import-linter (`.importlinter`) | 001–003, 005, 006, 008, 011–015, 017, 034, 035 | CI + pre-commit |
| Import-graph queries / bespoke asserts | grimp | 007, cycle detection, "who imports X" | pytest arch suite |
| Banned symbols/patterns per layer | ruff (`flake8-tidy-imports` banned-api, `TID`, `TCH`) | 003, 004, 028 | CI + pre-commit |
| AST structural rules | custom `ast` checker shipped with the standard | 023, 031, 018, 019, 030, 040 | CI + pytest |
| Package boundaries with a public API | tach (`tach.toml`) | 012, 042, 045 | CI |
| Event schema / contract testing | pydantic/jsonschema export + consumer fixtures; optionally Pact | 024, 043, 044 | CI (producer & consumer) |
| Test taxonomy | pytest markers + a conftest rule forbidding infra imports in domain tests | 038 | CI |
| Coverage gates per layer | coverage.py with per-path thresholds | Section 11.5 | CI |
| Manual review checklist | shipped PR checklist for the "manual" rules | 016, 021*, 027, 029, 036, 039, 042 | code review |

### 14.2 Confidence tiers

- **full** (~20 rules): deterministic pass/fail on the exact rule.
- **partial** (~14 rules): catches common violations; edge cases need review.
- **manual** (~6 rules): only a human or an LLM reviewer can judge.

### 14.3 The validator

A single entrypoint `python -m arch_standard.check` runs import-linter + the AST checker +
schema validation and prints:

```text
ARCH-001  PASS
ARCH-012  FAIL  sales/application/order_placement.py:4  imports billing.domain.invoice
ARCH-023  FAIL  sales/domain/model/events.py:12         OrderCreate is not past-tense / not frozen
```

Exit non-zero on any MUST failure; warn on SHOULD.

---

## 15. Progressive Structure — thresholds

| Signal | Threshold (starting point, tune per project) | Action |
|---|---|---|
| `domain/model.py` size | > ~400 lines or > 2 aggregates | promote to `domain/model/` package |
| `domain/model/ports.py` | > ~8 port definitions | split into `ports/` (`repositories.py`, `services.py`) |
| Application service class | > ~7 methods, or incohesive constructor deps | split into a second capability service |
| Reads through the aggregate | complex joins, reporting, dashboard shapes | introduce a dedicated read model outside the domain |
| Context sub-areas | 2+ separable areas each with its own aggregates | activate the `<module>/` level |
| Cross-context integration | > 1 team, or independent deployability needed | move from in-process gateway to async events + ACL as the default |
| Infrastructure adapters of one kind | many (e.g. 5+ external clients) | sub-folder within `infrastructure/` |

---

## 16. Reuse pipeline

```text
architecture-standard/   (this repo — canonical)
├── ARCHITECTURE_STANDARD.md          # human spec (English), generated from rules/ + prose
├── rules/*.yaml                      # machine-readable catalog — source of truth
├── checks/                           # the validator: import-linter template + AST checker + schema tools
├── templates/                        # project skeleton (copier)
├── skills/architecture/SKILL.md      # the Superpowers skill
└── reviewers/architecture-reviewer/  # subagent definition
```

Consumption paths:

1. **Human** — reads `ARCHITECTURE_STANDARD.md`.
2. **New project** — `copier copy` → `src/` skeleton + `.importlinter` + CI + `check` command.
3. **Superpowers skill** — triggers on "new bounded context", "add a use case", "where does X go", "review architecture". Loads the relevant rule subset + the decision trees. Points Claude Code at `rules/*.yaml`.
4. **architecture-reviewer subagent** — given a diff, loads `rules/`, runs `checks/`, judges the "manual" rules with an LLM, posts an `ARCH-xxx PASS/FAIL` report as PR comments.
5. **CI** — `checks/` on every PR; MUST failures block.

Authoring constraints for agent-consumability:
- every rule: stable ID, single level, `automation` field, one-paragraph rationale, one
  correct + one incorrect example;
- rule catalog is YAML (source of truth); Markdown is generated;
- decision guidance as decision trees / checklists, not prose;
- structure as a literal tree + a "what goes where" table;
- every rule is self-contained — no "as discussed above".

### 16.1 `ARCHITECTURE_STANDARD.md` outline

```text
0.  Purpose, scope, how to read (RFC 2119), version/status
1.  Philosophy
2.  Structure — canonical tree; "what goes where"; the two commons tiers; the module level
3.  Bounded Contexts — ownership; isolation; communication; Published Language; extraction path
4.  Entry points — the flow; entrypoint-as-adapter; providers; allowed/forbidden; exceptions
5.  Domain — model/ contents; tactical patterns (when yes/no); ports; exceptions; projections
6.  Application — service per capability; one method per use case; commands; UoW; integration events; domain-vs-application
7.  Infrastructure — outbound adapters; data mapper; UoW; outbox
8.  commons/ and shared_kernel/ — the two tiers; allow/forbid; the "encodes policy?" test; governance
9.  Dependency Rules — full catalog from rules/*.yaml
10. DDD Rules — decision trees
11. Testing Strategy
12. Anti-patterns
13. MUST / SHOULD / MAY — levels; exception (ADR) process
14. Architecture as Code — tooling map; validator; confidence tiers; CI
15. Progressive Structure — the thresholds table
16. Reuse — the pipeline
17. Open decisions / trade-off log (living)
18. Glossary
A.  rules/ YAML schema
B.  reference .importlinter + check command
C.  ADR template for exceptions
```

### 16.2 `rules/*.yaml` schema (Appendix A)

```yaml
id: ARCH-012
name: Context isolation
level: MUST            # MUST | SHOULD | MAY | MUST*
automation: full       # full | partial | manual
category: dependencies
description: >
  A bounded context imports nothing from another bounded context.
rationale: >
  Keeps contexts substitutable and independently deployable; a change inside one
  context cannot break another; the contract between teams stays explicit.
correct: |
  # sales needs a credit check
  # sales/domain/model/ports.py declares CreditCheckPort (consumer-driven)
  # bootstrap/ wires an adapter backed by billing's application service
incorrect: |
  from billing.domain.invoice import Invoice   # in sales/
validation:
  tool: import-linter
  contract: independence
```

---

## 17. Open decisions / trade-off log

Resolved in this spec (see Section 0). Remaining items for v1.1+:

| # | Item | Note |
|---|---|---|
| A | Concrete threshold numbers in Section 15 | Starting points given; calibrate against the first 2–3 real projects |
| B | `EventBus` in `domain/model/ports.py` vs a dedicated messaging contract module | Currently in domain ports for simplicity |
| C | Multi-repo (service-per-context) topology | Deferred to v2; v1 contracts are written to make it possible |
| D | Async runtime variant | Deferred; v1 is synchronous. An async appendix may follow |
| E | Standard-owned base classes vs pure conventions | Lean toward minimal base classes in `commons/` + conventions elsewhere |
| F | ADR allowlist format consumed by the validator | To be designed with `checks/` |

---

## 18. Known risks (from the design review)

1. **Service-class-per-capability** can drift from functional to logical cohesion —
   mitigated by ARCH-030 guardrails + lint on method count / file length; still needs
   review discipline.
2. **All ports in `domain/model/ports.py`** risks slow semantic erosion of the domain
   vocabulary — mitigated by ARCH-042 (non-domain contracts are colocated Protocols).
3. **Hot files** (`ports.py`, capability services) create merge contention — accepted
   cost of fewer files vs one-handler-per-file.
4. **ACL on both ends of cross-context interaction** is real ongoing mapping cost —
   mitigated by Progressive Structure (in-process gateway until >1 team) and the
   Published Language catalog.
5. **ARCH-021 as MUST-with-justification** — if routinely waived, the extraction path
   silently closes; the ADR expiry/review keeps waivers visible.
6. **Cross-context debugging through a broker** (when async) requires correlation IDs and
   event tracing as mandatory infrastructure — ARCH-043.

---

## Next step

Per the brainstorming workflow: review this spec in cold. On approval, the
`writing-plans` skill produces the implementation plan for v1 artifacts
(`ARCHITECTURE_STANDARD.md`, `rules/*.yaml`, `checks/`, `templates/`,
`skills/architecture/`, `reviewers/architecture-reviewer/`).
