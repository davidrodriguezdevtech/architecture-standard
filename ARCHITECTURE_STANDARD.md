# 0. Purpose, Scope, and How to Read

## Purpose and scope

This standard defines how application code is organized: business boundaries at the
top level, Clean/Hexagonal layering inside each boundary, and a catalog of
verifiable dependency and design rules. It is rule-based, deterministic, and
verifiable so that it is consumable by humans, by Claude Code, by an
architecture-reviewer agent, and by CI.

The following framing decisions are fixed for v1:

- **Language ecosystem.** Python first. Principles are written language-agnostic;
  concrete tooling and examples are Python (import-linter, grimp, ruff, pytest, tach).
- **Deployment topology.** Modular monolith by default. Bounded-context boundaries and
  contracts are defined as if the contexts were separable; physically the system stays
  one deployable.
- **Naming language.** English for all identifiers, folders, rule IDs, and for this
  standard.
- **Ports.** `typing.Protocol` (structural typing; adapters do not inherit). Three
  homes: `commons/types/` (generic technical protocols), the aggregate module's
  `domain/model/ports.py` (domain vocabulary), and colocated in the use-case module
  (non-domain outbound). There is no `application/ports.py` by default.
- **Persistence.** The normative contract (the `UnitOfWork` Protocol, repository ports,
  translation living in `adapters/`) is store-agnostic. SQLAlchemy is the shipped
  reference implementation, with an `InMemoryUnitOfWork` for tests. Other stores
  (DynamoDB, sqlite, and others) provide their own `UnitOfWork` and repositories against
  the same contract.
- **Error handling.** Exceptions are the standard mechanism. `DomainError` covers
  expected business errors. There is no `Result` / `Either` type in the core.
- **Runtime model.** Synchronous. Ports, repositories, Unit of Work, and handlers are
  `def`, not `async def`.
- **Identifier generation.** Application-generated (`next_identity()`, UUIDv7).
  Repositories receive aggregates whose identity is already assigned.
- **Input validation.** Pydantic at the edge (entrypoints) only. Business invariants
  live in the domain. Commands are frozen dataclasses. Pydantic MUST NOT appear in
  `domain/` or `application/`.
- **Event publication.** A transactional outbox is mandatory when delivery or
  transactional side-effect guarantees are required; optional otherwise.
- **Read models.** Domain-derived projections live in the aggregate module's
  `domain/model/projections.py`. Query, dashboard, and presentation read models live
  outside the domain, in `<context>/read/`, introduced when complexity justifies them.
- **Mapping (domain to DTO).** Manual mapping for domain-facing boundaries. Libraries
  are allowed for mechanical mapping at adapter and transport boundaries.
- **Cross-context communication.** Synchronous by default, contract-mediated, wired in
  `bootstrap/`, with zero imports between contexts. Asynchronous integration events
  when the use case explicitly tolerates eventual consistency.
- **Structural levels.** Two: the bounded context (`sales/`), then the aggregate module
  (`users/`), which is 1:1 with an aggregate. There is no context-level
  `application/`. `<context>/shared/` is the only context-level code area, and it is
  strictly limited.
- **Cross-aggregate flow.** Choreography by domain events; one service call per
  entrypoint handler. There is no orchestration layer, and none appears in the
  canonical tree. A synchronous request that needs two aggregates answers with
  `202 Accepted` or a partial synchronous write.
- **Integration events.** Conditional. They do not appear in the default shape. A
  domain event that starts being consumed by another context is promoted to a
  contract with a versioned schema.
- **Process wiring.** `main.py` is the process entrypoint. `bootstrap/` is the
  Composition Root.
- **Distribution.** The standard is the base of many repositories, one per project.
  Three semver'd artifacts exist: the standard (`arch-standard`), the shared technical
  package (`arch-commons`), and the project template. Projects carry a
  `.arch-standard` version stamp. A new MUST lands as a SHOULD in a minor release
  first, and becomes a MUST in the next major.
- **`commons/`.** Not vendored. `arch-commons` is an installed, separately versioned
  dependency, so a fix reaches every project instead of drifting into N copies.
- **Read side.** Repositories persist and retrieve aggregate roots; they are not
  query interfaces. Projection, reporting, search, dashboard, and cross-aggregate
  reads live in `<context>/read/`, which may query the store directly and returns
  DTOs.
- **Context dependencies.** Declared in `contexts.toml` and validated acyclic - the
  only way to see a cycle, since contexts never import each other.
- **Rule tiers.** Each rule is tagged `tier: core` or `tier: full`. The core rules
  bind from day one; `arch-standard check --core` runs only those.
- **Logging.** `domain/` and `application/` do not log. They raise domain exceptions
  and emit domain events; entrypoints and outbound adapters log.

## How to read this document (RFC 2119)

Rule levels follow RFC 2119:

- **MUST** is an architectural invariant. A violation fails the build and blocks merge.
  An exception requires a documented ADR and standard-maintainer approval.
- **SHOULD** is a strong default. Deviation is allowed with a one-line justification in
  the pull request or an ADR, and the reviewer must acknowledge it.
- **MAY** is a genuine project choice. It is documented so that it reads as sanctioned
  rather than accidental.

`MUST*` marks a conditional MUST: it applies whenever the stated condition holds
(for example ARCH-021 and ARCH-036).

---

# 1. Philosophy

Organize code by business first, then apply Clean/Hexagonal inside each business
capability. The top architectural level represents business boundaries (bounded
contexts), never technology (`controllers/`, `services/`, `repositories/`).

Three load-bearing ideas:

1. **The Dependency Rule.** Source-code dependencies point inward:
   `entrypoints -> application -> domain`, and `adapters -> domain/application`.
   The domain depends on nothing. Adapters are plugged in, never imported by the
   core.

2. **Business-capability cohesion at the top.** A change to "how orders work" touches
   one context. A change to "how we talk to Postgres" touches one adapter module.

3. **Fixed shape, growing content.** The folder structure is canonical and identical
   in every project built on this standard; what grows is the set of files inside it.
   A file does not exist until it has content, but its location is decided in
   advance. There is no "start flat, restructure later" step and therefore no
   judgement call about when to restructure - which is the point: the standard exists
   to make "where does this go?" answerable without judgement. The thresholds in
   Section 15 flag model problems, not layout problems.

The standard is rule-based, deterministic, and verifiable so that it is consumable by
humans, by Claude Code, by an architecture-reviewer agent, and by CI.

---

# 2. Structure

## 2.1 Canonical tree

```text
project/
├── main.py                          # process entrypoint: starts the app, calls bootstrap/
├── pyproject.toml
├── .importlinter                    # dependency contracts
├── contexts.toml                    # declared context dependency graph (Section 3.7)
├── .arch-standard                   # standard-version stamp (versioning policy: see the release notes)
├── src/
│   ├── <context>/                   # LEVEL 1 - one bounded context (e.g. sales)
│   │   ├── entrypoints/             # inbound adapters, context-wide
│   │   │   ├── http.py              #   HTTP/GraphQL
│   │   │   ├── events.py            #   message/event consumers
│   │   │   ├── cli.py               #   CLI
│   │   │   ├── cron.py              #   scheduled jobs
│   │   │   └── providers.py         #   thin: pulls wired services from the container
│   │   ├── shared/                  # ONLY what crosses this context's aggregates
│   │   │   ├── ids.py               #   ID types of this context's aggregates
│   │   │   ├── value_objects.py     #   policy-free VOs used by 2+ aggregates
│   │   │   └── services.py          #   domain services spanning aggregates (rare)
│   │   ├── <aggregate_module>/      # LEVEL 2 - 1:1 with an aggregate (e.g. users)
│   │   │   ├── domain/
│   │   │   │   ├── model/
│   │   │   │   │   ├── aggregate.py       # the aggregate root and its entities -
│   │   │   │   │   │                      #   a fixed name, not derived from the aggregate
│   │   │   │   │   ├── value_objects.py
│   │   │   │   │   ├── events.py          # domain events (frozen, past tense)
│   │   │   │   │   ├── ports.py           # domain-vocabulary ports (repository, ...)
│   │   │   │   │   ├── projections.py     # domain-derived read projections (when they exist)
│   │   │   │   │   └── exceptions.py
│   │   │   │   ├── services/              # domain services for this aggregate (optional;
│   │   │   │   │   └── <aggregate>.py     #   a directory - one file per service, named after
│   │   │   │   │                          #   the aggregate when there's only one (e.g.
│   │   │   │   │                          #   quote.py for Quote); 2+ services each get a
│   │   │   │   │                          #   descriptive name instead. Pure domain logic
│   │   │   │   │                          #   only - no I/O, no persistence queries (the
│   │   │   │   │                          #   repository's job, not a domain service's)
│   │   │   │   └── specifications.py      # optional
│   │   │   ├── application/
│   │   │   │   └── <aggregate>.py         # one method per use case
│   │   │   └── adapters/
│   │   │       ├── <aggregate>_repository.py
│   │   │       ├── mapping.py             # aggregate to stored-form translation
│   │   │       └── <adapter>.py           # one module per outbound adapter
│   │   ├── <aggregate_module_2>/    # same shape, one per aggregate
│   │   └── read/                     # Read/Query layer - projections, reporting, search,
│   │                                 #   dashboards, cross-aggregate reads. Returns DTOs.
│   │                                 #   Imports no aggregate module's domain/ or
│   │                                 #   application/. May query the store directly.
│   ├── shared_kernel/                # governed cross-context domain VOs.
│   │                                 #   Not scaffolded until genuinely needed.
│   └── bootstrap/                    # Composition Root: config, singletons, DI container,
│                                     #   service/UoW factories, router registration,
│                                     #   consumer startup
└── tests/
```

`adapters/` holds a module's **outbound (driven) adapters**: repositories, gateways,
clients. `entrypoints/` holds the context's **inbound (driving) adapters**: HTTP, consumers,
CLI. Both are adapters; the folder names say which side of the core they sit on.

`commons/` is not part of `src/`. It is an installed, separately versioned package
(`arch-commons`) that every project depends on, so a fix reaches all of them at once
(Section 8.1). `shared_kernel/` stays in the repository - it holds this project's own
cross-context domain concepts.

The folder shape is fixed and canonical. Files appear when they have content. A
context does not start as loose modules and get restructured later:
`value_objects.py` does not exist until there is a value object, but the moment there
is one, its location is already determined. There is no decision to make and no import
refactor to do, and every project built on this standard has the same shape.

## 2.2 The two structural levels

| Level | Folder | Term | What it is |
|---|---|---|---|
| 1 | `sales/` | Bounded Context | a business boundary with its own ubiquitous language |
| 2 | `users/` | Aggregate module | 1:1 with an aggregate. Not a bounded context and not a subdomain |

`subdomain` is a DDD problem-space term (core, supporting, generic) and is never a
folder. A bounded context is the solution-space boundary that implements one.

The 1:1 rule is what makes "where does this go?" answerable without judgement: the
aggregate's name is the folder's name. It also makes the one-transaction-per-aggregate
rule (Section 5.3) visible in the tree - a use case touching two aggregate modules is
visibly crossing a line.

Isolation between aggregate modules is weaker than between contexts. They share the
context's ubiquitous language. An aggregate module MUST NOT import another aggregate
module's `application/` or `adapters/`; references between aggregates are by ID,
and those ID types live in `<context>/shared/ids.py`. (ARCH-046)

## 2.3 What goes where

| You are adding... | It goes in... |
|---|---|
| A new business boundary | `src/<context>/` |
| A new aggregate | `src/<context>/<aggregate_module>/` (a new folder, full shape) |
| A rule that protects an invariant of one aggregate | a method on the aggregate in `<module>/domain/model/aggregate.py` |
| A calculation over one aggregate that is not a method | `<module>/domain/services/` (one file per domain service; named after the aggregate if there's only one, e.g. `quote.py`) |
| A calculation spanning aggregates of the same context | `<context>/shared/services.py` |
| A use case (state change on one aggregate) | a method on `<module>/application/<aggregate>.py` |
| A persistence/broker/third-party integration | one module in `<module>/adapters/` |
| A contract the domain needs | `<module>/domain/model/ports.py` |
| A non-domain outbound contract used by one use case | a `Protocol` colocated in that `application/` module |
| A fact other parts of this context react to | a domain event in `<module>/domain/model/events.py` |
| An ID type referenced by another aggregate of this context | `<context>/shared/ids.py` |
| A value object used by 2+ aggregates of this context | `<context>/shared/value_objects.py` |
| A projection, report, search, dashboard, or any cross-aggregate read | `<context>/read/` |
| A dependency-free technical primitive | the `arch-commons` package, `commons.types` (propose upstream) |
| A shared framework-bound technical implementation | the `arch-commons` package, `commons.adapters` (propose upstream) |
| A domain concept genuinely shared by 2+ contexts, with business policy | `shared_kernel/` (with governance) |
| Wiring / config / DI | `bootstrap/` |

## 2.4 There is no context-level `application/`

DDD has no "application service of the context" - application services are per use
case and belong with the model they coordinate. Cross-aggregate flow is handled by the
rules in Section 3.6, not by a coordinating layer.

`<context>/shared/` is the only context-level code area, and it is strictly limited to
the three things in the table above: ID types, policy-free value objects used by 2+
aggregates, and domain services spanning aggregates. It never holds a service, a
repository, or an aggregate. (ARCH-047)

## 2.5 The Read/Query layer

Repositories are responsible for persistence and retrieval of aggregate roots. They
must not be used as general-purpose query interfaces. Complex, projection-oriented,
reporting, search, dashboard, or cross-aggregate reads belong to the Read/Query layer.

`<context>/read/` is that layer. It exists at context level, not inside an aggregate
module, because the reads that need it are precisely the ones that span aggregates - a
single-aggregate lookup is served by that aggregate's repository.

- `read/` MAY query the store directly, bypassing aggregates and the Unit of Work.
  That is the point: a read model is not bound by write-side invariants.
- `read/` MUST NOT import any aggregate module's `domain/` or `application/`.
  (ARCH-052)
- `read/` returns DTOs, never aggregates.
- Entrypoints call `read/` directly for queries; they do not route a query through an
  application service that adds nothing.

This keeps the CQRS split explicit and mechanically checkable, and it keeps the write
side (aggregate modules) free of query pressure. (ARCH-051, ARCH-052)

---

# 3. Bounded Contexts

## 3.1 Rules

- The first level of `src/` is bounded contexts. Each context owns its own model,
  language, and rules.
- A context MUST NOT import another context's internals (`domain/`, `application/`,
  `adapters/`). Zero imports between contexts. (ARCH-012)
- Contracts (ports, event schemas, boundary DTOs) are defined as if the contexts were
  physically separable.
- No dependency cycles between contexts. (ARCH-013)

## 3.2 Communication - decision order

| Situation | Mechanism |
|---|---|
| Consumer needs data/decision from another context now, and staleness is unacceptable | Synchronous, contract-mediated. The consumer declares its own consumer-driven port; `bootstrap/` wires an adapter backed by the other context's application service; the consumer's `adapters/<x>_gateway.py` implements the port and does the ACL. Zero imports between contexts. |
| The use case explicitly tolerates eventual consistency; or fan-out to many consumers; or crossing a future service boundary | Asynchronous integration events. The producer publishes a versioned, serialized event; each consumer has an ACL translating the raw message to its own model. Published via transactional outbox when delivery must be guaranteed. |
| Producer needs a consumer to do something | Send a command, not an event. Events are facts (past tense); they never oblige a handler. |
| A concept looks shared but means different things in each context | Duplicate. Each context models its own. Sharing is the exception. |

## 3.3 Anti-Corruption Layer

Every inbound translation from another context (a synchronous response or an
asynchronous message) passes through an ACL in the consumer's `adapters/`. The
ACL is the only place that knows the other context's contract shape; the rest of the
consumer sees only its own model.

## 3.4 Published Language - conditional

Integration events do not exist by default. Until a context actually publishes to
another context asynchronously, every event is a domain event living in its aggregate
module's `domain/model/events.py`. Introducing an integration-event module before
there is a consumer is speculative.

The promotion rule: a domain event that starts being consumed by another context stops
being internal and becomes a contract. At that moment it is promoted out to a
dedicated module and acquires a versioned schema in an events catalog - expressed as
schema (JSON Schema / Avro / Pydantic export), never as an importable class. From then
on, changing it is a contract change.

Without this rule, someone subscribes to an internal domain event and every subsequent
refactor silently becomes a breaking change for another team. (ARCH-024, ARCH-044 -
both conditional MUSTs, applying once a context publishes integration events.)

## 3.5 Extraction path

Because adapters sit behind ports and cross-context contracts are already
explicit, extracting a context to its own service means: replace the in-process
gateway adapter with an HTTP client, and replace the in-process bus with a real broker.
`domain/` and `application/` are untouched.

## 3.6 Cross-aggregate flow within a context

A use case that spans two aggregates cannot be one transaction (Section 5.3), so there
is nothing atomic to orchestrate. The rules, in order:

1. Default - choreography by domain events. `users` emits `UserRegistered`;
   `entrypoints/events.py` consumes it and makes one call to
   `subscriptions/application/subscription.py`. One service call per
   entrypoint handler. This is an inbound adapter doing its job, not orchestration.
2. Never sequence multi-step flow inside an entrypoint handler. Sequencing and
   compensation are logic: they would only be testable through the transport, they get
   rewritten per transport, and it is the Fat Controller anti-pattern (Section 12). It
   also breaks the hexagonal criterion that the application must be drivable from a
   test with no adapter attached.
3. Synchronous multi-aggregate requests (an endpoint that must return a result derived
   from two aggregates) have two sanctioned answers: return `202 Accepted` plus a
   resource to poll, or make only the first aggregate's write synchronous and return
   its id, letting the rest happen asynchronously.
4. Diagnostic - this is the most valuable of the four. If atomicity across two
   aggregates is frequently needed, the aggregate boundaries are drawn wrong. Redraw
   them before reaching for any coordinating construct.

There is deliberately no orchestration module in the canonical tree. If a genuine
long-running business process later demands one, the DDD pattern is a Process Manager
(stateful, tracks its own progress, lives in the application layer) - introduced as a
named exception with its own review, never as a general-purpose coordination layer.

## 3.7 Declared context dependency graph

Contexts do not import each other (ARCH-012), so no static import analysis can see a
cycle between them: a runtime cycle `sales -> billing -> sales` through
`bootstrap/`-wired gateways is invisible to every other check in this standard.

The fix is a declaration. `contexts.toml` at the project root lists, for each context,
the contexts it is allowed to depend on:

```toml
[contexts.sales]
depends_on = ["billing"]

[contexts.billing]
depends_on = []

[contexts.identity]
depends_on = []
```

- Every cross-context dependency wired in `bootstrap/` MUST correspond to a declared
  edge.
- The declared graph MUST be acyclic.
- Adding an edge is a deliberate, reviewable act - which is the real value: it turns
  "someone quietly wired B into A" into a diff.

(ARCH-050)

---

# 4. Entry Points

## 4.1 Flow

```text
External stimulus -> Entrypoint -> Application use case -> Domain
```

## 4.2 Rules

- Entrypoints are inbound adapters: HTTP, GraphQL, Kafka/RabbitMQ/SQS consumers, CLI,
  cron.
- An entrypoint translates a stimulus into a command/query, calls one application
  service method, and maps the result or exception back to the transport (status codes,
  serialization). (ARCH-004 family)
- An entrypoint obtains a fully wired service from
  `<context>/entrypoints/providers.py` (which pulls from the `bootstrap/` container).
  It MUST NOT construct outbound adapters itself. (ARCH-009)
- An entrypoint MUST NOT call persistence, adapters, or the database directly
  (`repo.save(...)`, `session.execute(...)`, `http_client.get(...)`). The only thing it
  calls is the application service. (ARCH-009)
- An entrypoint MUST NOT contain business logic. (ARCH-010, SHOULD)
- An entrypoint MUST NOT call another entrypoint. (ARCH-011)
- An entrypoint MAY import `domain/model/exceptions.py` (and the `commons` base errors)
  solely to map domain exceptions to transport responses.
- Pydantic request/response models live only in entrypoints.

## 4.3 Exceptions to the rule

- Health and readiness endpoints MAY read backing-service state directly; they are not
  business use cases.
- A pure pass-through admin or debug endpoint MAY be exempt if it is explicitly marked
  and excluded from the public surface. This is discouraged and requires justification.

---

# 5. Domain

## 5.1 Contents and dependencies

`domain/` contains: `model/` (aggregates, entities, value objects, domain events,
ports, projections, exceptions), `services/` (one file per domain service; named
after the aggregate when there's only one, e.g. `quote.py`), and `specifications.py`.

`domain/` depends on: the standard library, `commons/types/`, and (rarely)
`shared_kernel/`. Nothing else. No frameworks, no I/O, no ORM, no `datetime.now()` or
`uuid4()` directly (use the `Clock` and `IdGenerator` ports), no application DTOs.
(ARCH-001 to ARCH-004)

## 5.2 Preference order

Start with a method on the aggregate. Extract to a domain service when logic spans
aggregates. Extract to a Policy, Specification, or Factory only with demonstrated
variation or reuse.

## 5.3 Tactical patterns - when to use, when not

**Value Object.** Use for a concept described by its values (`Money`, `Email`,
`DateRange`, `Quantity`), with no lifecycle, that needs centralized validation and
value equality. Do not use it when it needs identity over time (use an Entity) or when
it is a bare primitive with no invariants (avoid wrapper obsession). Implement with
`@dataclass(frozen=True)`, validate in `__post_init__`, no setters; methods return new
instances. (ARCH-031)

**Entity.** Use when the concept has a stable identifying ID even as attributes change
and its history matters. Do not use it when it is interchangeable by value (use a Value
Object) or when it exists only inside another entity and is never referenced from
outside. Identity is by ID, mutation only via business-named methods, no setters that
enable invalid state. (ARCH-018)

**Aggregate and Aggregate Root.** Use when invariants span several objects and must
always hold. Do not lump unrelated objects together. Access and mutate only via the
root (ARCH-019); reference other aggregates by ID (ARCH-020); one transaction modifies
one aggregate (ARCH-021, MUST with documented justification); validate invariants on
every mutation. The God Aggregate smell: more than roughly 7 invariants, or hundreds
of loaded children.

**Domain Service.** Use when logic involves multiple aggregates and belongs to none,
or needs a domain port. Do not use it when the logic fits on an aggregate (that yields
an anemic domain), when it is orchestration (use an application service), or for a pure
calculation over one aggregate (use an aggregate method). Stateless, takes aggregates
and value objects as parameters, does I/O only via `domain/model/ports.py`, and knows
nothing about transactions or DTOs.

**Domain Event.** Use when another part of the same context reacts to a state change in
a decoupled way, or when the fact must be recorded to derive integration events. Do not
use it when the reaction is part of the same invariant and transaction, or when it is
cross-context communication (use an integration event). `frozen`, past tense, no
side-effects, carries `occurred_at` plus the needed IDs. Dispatched after persistence.
(ARCH-023)

**Repository (abstraction).** Use when an aggregate root needs persistence and
retrieval by identity or specification. Do not use it for complex multi-aggregate read
queries (use a read model); do not add `find_x_with_y() -> DTO` (Repository as business
service). The interface lives in `domain/model/ports.py`, methods are at root level
(`get`, `add`, `save`, `next_identity`), and it returns aggregates, not rows or DTOs.
(ARCH-022)

**Factory.** Use when building a valid aggregate needs non-trivial logic, or when
reconstruction from persistence differs from fresh creation. Do not add a factory that
only wraps the constructor. Prefer a `@classmethod` on the aggregate
(`Order.place(...)`) unless the logic is large or needs a port.

**Specification.** Use when the same selection or validation rule is used in 2+ places,
or when rules combine dynamically. Do not use it for one-off rules
(`order.is_cancellable()`) or purely to filter in the database. Stateless,
`is_satisfied_by(candidate) -> bool`.

**Policy.** Use when there are multiple real strategies for a decision chosen at
runtime. Do not use it for a single rule, or when "policy" actually means
authorization or rate-limiting (that is an application or adapter concern). The interface
and its implementations live in `domain/`.

## 5.4 Exceptions

Concrete domain exceptions live in `domain/model/exceptions.py`, subclassing
`commons.types.errors.DomainError`. The domain never raises library exceptions.
(ARCH-032) `DomainError` also covers expected business errors (validation, precondition
failures) - there is no `Result` type.

## 5.5 Projections versus the Read/Query layer

A domain-derived projection - a read shape computed from the aggregate, still
expressed in domain terms and used by the write side - lives in the aggregate
module's `domain/model/projections.py`.

Everything else is not domain. Repositories persist and retrieve aggregate roots and
must not be used as general-purpose query interfaces (ARCH-051). Projection-oriented,
reporting, search, dashboard, and cross-aggregate reads belong to `<context>/read/`
(Section 2.5), which may query the store directly and returns DTOs.

The practical test: if the result is an aggregate, or a value derived from one
aggregate for the write side, it is domain. If the result is a DTO shaped for a
screen, a report, or a search result, it is the read layer.

---

# 6. Application

## 6.1 Responsibility

Coordinate use cases for this module's aggregate: load it, invoke its business
method, persist via the Unit of Work, publish domain events, map domain to DTO,
control the transaction boundary, and enforce use-case-level authorization. No
business invariants - those are in the domain. (ARCH-005 to ARCH-007, ARCH-027,
ARCH-029)

## 6.2 Shape

One application service class per aggregate module; one public method per use case.
This follows from the 1:1 aggregate-module rule (Section 2.2): there is no "general
service that splits later," and no context-level application layer. The day-1 shape
is the steady-state shape. (ARCH-030, SHOULD)

```python
# sales/orders/application/order.py
@dataclass(frozen=True)
class CreateOrder:
    customer_id: str
    lines: tuple[OrderLineInput, ...]

class OrderNotifier(Protocol):           # colocated non-domain outbound contract
    def order_placed(self, order_id: OrderId) -> None: ...

class OrderService:
    def __init__(
        self,
        uow: UnitOfWork,
        orders: OrderRepository,        # injected already bound to `uow`
        bus: EventBus,
        notifier: OrderNotifier,
    ) -> None: ...

    def create_order(self, command: CreateOrder) -> OrderId:
        with self._uow:
            order = Order.place(CustomerId(command.customer_id), command.lines)
            self._orders.add(order)
            self._uow.commit()
        self._bus.publish_all(self._uow.collect_new_events())
        return order.id

    def cancel_order(self, command: CancelOrder) -> None: ...
    def add_item(self, command: AddItemToOrder) -> None: ...
```

Guardrails (ARCH-030):

- One method equals one use case equals one transaction, on this module's aggregate.
- Zero business rules in the service. An `if` about business meaning moves to the
  domain.
- A method that needs to change a second aggregate is a design signal, not a licence
  to reach across - see Section 3.6.
- The checker warns past roughly 7 public methods, 200 lines, or 5 constructor
  parameters. At that size the aggregate itself is usually doing too much - look at
  the aggregate before splitting the service.
- Naming follows the aggregate: `OrderService` in `orders/`, `UserService` in
  `users/`.
- Command objects are frozen dataclasses; they may live in the same module as the
  service.

## 6.3 Ports

Inbound versus outbound:

- **Domain ports** (repositories, domain-service providers) are indispensable. DIP
  requires them - the core must not name adapters. MUST.
- **The application inbound port** is the use-case / service class itself, exposed to
  entrypoints. Its public methods are the port. There is no separate interface.
- **Application outbound ports** that are not domain vocabulary (`EmailSender`,
  `PaymentGateway`, cross-context gateways): the explicit `Protocol` is optional
  (SHOULD) - write it when the seam benefits from being explicit (testing,
  type-checking, multiple implementations, agent-readability), and skip it
  (duck-typed injection) for a trivial single-implementation dependency. Injection is
  never optional: the concrete adapter is built in `providers.py` and injected;
  `application/` never imports it.

Three homes, one rule each:

| Home | What lives here | The test |
|---|---|---|
| `commons/types/` | generic technical Protocols: `Clock`, `UnitOfWork`, `EventBus`, `IdGenerator` | dependency-free, no business meaning, reusable in any project |
| `domain/model/ports.py` | domain-vocabulary contracts: repositories, domain-service providers (`PricingPolicyProvider`) | you would mention it describing the business; a domain object or the repository abstraction needs it |
| a `Protocol` colocated in the use-case module | non-domain outbound contracts the orchestration needs: `EmailSender`, `PaymentGateway`, cross-context gateways (`CreditCheckPort`) | only `application/` uses it; it is integration plumbing, not domain language |

- No `application/ports.py` file by default - colocated `Protocol`s are the mechanism.
  (ARCH-042, SHOULD)
- Promote to `application/ports.py` only when a context has 3+ application ports
  shared across multiple use-case modules (Progressive Structure, Section 15).
- Rationale: this keeps `domain/model/ports.py` a faithful list of domain concepts and
  keeps integration-contract churn out of the stable domain file.

## 6.4 Integration events - conditional, not in the default shape

There is no `integration_events.py` in the canonical tree. Until this context
publishes to another context asynchronously, all events are domain events in their
aggregate module's `domain/model/events.py`.

When the promotion rule in Section 3.4 fires - another context starts consuming one
of this context's events - the promoted event moves to a dedicated module at the
context root, gains a versioned schema in the events catalog, and every publish wraps
it in the `commons/` `EventEnvelope` (correlation and causation IDs, type, version) so
async flows stay traceable (ARCH-043). Consumers never import that module; they see
serialized envelopes only.

## 6.5 Domain logic versus application orchestration

| Domain logic | Application orchestration |
|---|---|
| "An order cannot exceed the customer's credit limit" | "Load the order, add the item, save, publish `ItemAdded`" |
| "A shipped order cannot be cancelled" | "Begin transaction, on failure roll back and publish nothing" |
| "Discount = policy applied to line totals" | "Map the HTTP body to a command; map the aggregate to a response DTO" |

---

# 7. Adapters

## 7.1 Rules

- One module per outbound adapter. No sub-folders by type. A sub-folder is used only
  when a context accumulates many adapters of one kind (an exception, not the norm).
- Adapters implement ports declared in `domain/model/ports.py`; the core imports
  abstractions only. (ARCH-008)
- No Active Record. The aggregate has no persistence base class, decorator, or import,
  and no `save()`. Translation between the aggregate and its stored form lives entirely
  in `adapters/`, in whatever form the store needs. (ARCH-028)
- Adapters contain no business logic and make no orchestration decisions.
- `adapters/` MAY import `commons/adapters/`; `domain/` and `application/`
  MUST NOT. (ARCH-034)

## 7.2 Unit of Work and persistence

### Normative contract (store-agnostic)

`commons/types/unit_of_work.py` holds the `UnitOfWork` Protocol. It owns the
transaction and domain-event collection. It says nothing about a specific database.

```python
class UnitOfWork(Protocol):
    def __enter__(self) -> "UnitOfWork": ...
    def __exit__(self, *exc: object) -> None: ...      # rollback if commit() was not called
    def commit(self) -> None: ...
    def rollback(self) -> None: ...
    def track(self, aggregate: object) -> None: ...    # repositories call this on load/store
    def collect_new_events(self) -> Iterable[DomainEvent]: ...
```

- Repository ports in `domain/model/ports.py` are collection-style, root-level (`add`,
  `get`, `next_identity`, specification queries), and return aggregates - never rows or
  DTOs. (ARCH-022)
- Repositories receive the UoW and run against the store handle it exposes; they call
  `uow.track(aggregate)` on every load and store so events can be drained.
- Translation between the aggregate and its stored form lives entirely in
  `adapters/`, in whatever form the store needs. The aggregate has no persistence
  knowledge. (ARCH-028)
- One transaction modifies one aggregate (ARCH-021) - this keeps the UoW portable to
  stores without general multi-item transactions.
- There is no per-context UoW class. The application layer talks only to named
  repository ports, never to the UoW's store handle. (protects ARCH-022, ARCH-029)

### Reference implementation - SQLAlchemy

Shipped in `commons/adapters/` and the template.

- `SqlAlchemyUnitOfWork` owns a `Session`; `collect_new_events()` iterates
  `session.new | session.dirty | session.identity_map` and drains each aggregate
  root's pending events (so `track()` is effectively implicit for this store).
- Per context: `adapters/mapping.py` holds `Table` definitions plus
  `map_imperatively(Order, order_table, ...)`. There is no separate ORM model class and
  no manual mapper. Domain classes stay free of ORM base classes, decorators, and
  imports. `bootstrap/` calls each context's `configure_mappings()` once at startup.
- The thin repository runs against `uow.session` and returns aggregates directly.
- `InMemoryUnitOfWork` (dict-backed, explicit `track()`) ships alongside for tests.

```python
# sales/orders/adapters/order_repository.py     - thin, intention-revealing
class SqlAlchemyOrderRepository:                  # implements OrderRepository (domain port)
    def __init__(self, uow: SqlAlchemyUnitOfWork) -> None:
        self._uow = uow

    def add(self, order: Order) -> None:
        self._uow.session.add(order)

    def get(self, order_id: OrderId) -> Order:
        order = self._uow.session.get(Order, order_id.value)
        if order is None:
            raise OrderNotFound(order_id)
        return order
```

A reporting-shaped method (`find_open_for_customer`, or anything else that filters or
lists rather than retrieves one aggregate root by identity) does not belong here - per
ARCH-051, that query lives in `sales/read/`, not on the repository (Section 2.5).

```python
# sales/entrypoints/providers.py
def order_service() -> OrderService:
    uow = unit_of_work()                          # from bootstrap/ (mappings already configured)
    orders = SqlAlchemyOrderRepository(uow)
    return OrderService(uow=uow, orders=orders, bus=event_bus(), notifier=notifier())
```

### Other stores

The same `UnitOfWork` Protocol, the same repository ports, and the same `track()` /
`collect_new_events()` contract apply - only the implementation changes:

- **DynamoDB:** `DynamoUnitOfWork` buffers writes and flushes on `commit()` as a
  conditional `PutItem` / `TransactWriteItems`; repositories serialize aggregates to
  items explicitly.
- **Raw sqlite or another driver:** the repository hand-writes row-to-aggregate
  translation (a `<aggregate>_mapper.py` with pure `to_row` / `to_aggregate` functions
  when it grows).

The manual-translation form is also the escape hatch for SQL projects whose aggregates
are hostile to imperative mapping (deeply immutable structures, computed state).

### Test note

Domain unit tests run without the store's mapping or translation configuration so
aggregate classes stay uninstrumented (guarded by a fixture). See Section 11.4. Every
use-case write goes through a UoW; the service never commits repositories
individually. (ARCH-033)

## 7.3 Transactional outbox

- Mandatory when event publication or a transactional side-effect requires a delivery
  or consistency guarantee: integration events are written to an `outbox` table in the
  same transaction; a separate process publishes them. (ARCH-036)
- Optional (`publish-after-commit`) when no such guarantee is required.
- The machinery lives in `commons/adapters/outbox.py`.

---

# 8. commons/ and shared_kernel/

## 8.1 `arch-commons` - a separately versioned package

`commons/` is not vendored into each project. It is published as `arch-commons` and
declared as a dependency, so a fix or a new primitive reaches every project that
upgrades instead of drifting into N divergent copies. This is what makes the standard
usable as the base of many repositories rather than a one-off scaffold.

| | `commons.types` | `commons.adapters` |
|---|---|---|
| Content | dependency-free technical primitives and Protocols | framework-bound shared implementations |
| Examples | `DomainError`/`ApplicationError` bases, `EntityId`, `Pagination`, `Clock` / `EventBus` / `IdGenerator` / `UnitOfWork` Protocols | `SqlAlchemyUnitOfWork`, `InMemoryUnitOfWork`, outbox machinery |
| Importable by | everyone, including `domain/` | only `adapters/`, `entrypoints/`, `bootstrap/`, tests |
| Forbidden | any business meaning, any framework import | - |

**Governance.** `arch-commons` follows semver, with the same compatibility policy as
the standard itself: a breaking change to `commons.types` is a major bump and is
announced with migration notes. Adding a primitive is a minor. Consuming projects pin
a version and upgrade deliberately.

**Contributing upward.** A technical primitive that a project invents locally, and
that a second project would want, does not get copied - it is proposed upstream into
`arch-commons`. Until it is accepted it lives in that project, clearly marked.

Rules: ARCH-015 (`commons.types` imports nothing from
contexts/application/adapters/shared_kernel), ARCH-016 (`commons.types` has no
business logic), ARCH-034 (`commons.adapters` not imported by
domain/application), ARCH-035 (`commons.types` imports no framework).

## 8.2 shared_kernel/

Deliberately shared domain concepts across 2+ contexts, with sign-off from every
consuming context. Only small, immutable, policy-bearing value objects - no entities,
aggregates, domain services, or repositories.

The test: does the concept encode a business policy?

- **No** (a typed wrapper plus format validation, e.g. `Email` syntax, `Money`
  arithmetic that raises on currency mismatch) goes to `commons/types/`. No ceremony.
- **Yes** (accounting rounding, tax rules, business-specific validation, an ID two
  contexts agree to share) goes to `shared_kernel/` with change governance.

Governance: a change requires review from every consuming context; the kernel is
versioned. It is not scaffolded until the first genuine shared policy-bearing concept
exists. (ARCH-014: `shared_kernel` imports nothing from any context.)

Generic subdomains (notifications, identity) are other bounded contexts, not shared
code - consumed via the Section 3 mechanisms.

---

# 9. Dependency Rules

Every rule carries the full schema: ID, name, description, rationale, correct example,
incorrect example, level (MUST/SHOULD/MAY), automation (full/partial/manual), and tier
(core/full). The machine-readable source of truth is `rules/*.yaml`; the tables below
are generated from it.

Each rule is tagged `tier: core` or `tier: full`. Core rules are binding from day one
and machine-checkable; `arch-standard check --core` runs exactly that set, and the
table below lists it before the full catalog.

### Core rules

Binding from day one. `arch-standard check --core` runs exactly these.

| ID | Rule | Level | Automation |
|---|---|---|---|
| ARCH-001 | Domain does not depend on adapters | MUST | full |
| ARCH-002 | Domain does not depend on application | MUST | full |
| ARCH-003 | Domain does not depend on frameworks | MUST | full |
| ARCH-005 | Application does not depend on adapters | MUST | full |
| ARCH-006 | Application does not depend on entrypoints | MUST | full |
| ARCH-008 | Adapters implement ports; the core imports abstractions only | MUST | partial |
| ARCH-012 | A context imports nothing from another context | MUST | full |
| ARCH-023 | Domain events are immutable and past-tense | MUST | full |
| ARCH-031 | Value Objects are immutable and validate on construction | MUST | partial |
| ARCH-033 | Every use-case write goes through a Unit of Work | MUST | partial |
| ARCH-046 | Aggregate module isolation | MUST | full |
| ARCH-051 | Repositories are not query interfaces | MUST | partial |

### dependencies

| ID | Rule | Level | Automation |
|---|---|---|---|
| ARCH-001 | Domain does not depend on adapters | MUST | full |
| ARCH-002 | Domain does not depend on application | MUST | full |
| ARCH-003 | Domain does not depend on frameworks | MUST | full |
| ARCH-004 | Domain performs no I/O | MUST | partial |
| ARCH-005 | Application does not depend on adapters | MUST | full |
| ARCH-006 | Application does not depend on entrypoints | MUST | full |
| ARCH-007 | Application does not construct concrete adapters | MUST | partial |
| ARCH-008 | Adapters implement ports; the core imports abstractions only | MUST | partial |
| ARCH-009 | Entrypoints obtain wired services from providers; never construct or call outbound adapters directly | MUST | partial |
| ARCH-010 | Entrypoints contain no business logic | SHOULD | partial |
| ARCH-011 | Entrypoints call application services, not other entrypoints | MUST | full |
| ARCH-012 | A context imports nothing from another context | MUST | full |
| ARCH-013 | No dependency cycles between contexts | SHOULD | full |
| ARCH-014 | shared_kernel imports nothing from any context | MUST | full |
| ARCH-015 | commons/types imports nothing from contexts, application, adapters, or shared_kernel | MUST | full |
| ARCH-016 | commons/types contains no business logic | MUST | manual |
| ARCH-017 | Nothing imports bootstrap | MUST | full |
| ARCH-034 | commons/adapters is not imported by domain or application | MUST | full |
| ARCH-035 | commons/types does not import any framework | MUST | full |
| ARCH-037 | Entrypoint wiring is defined in per-context providers.py, backed by bootstrap | MUST | partial |

### model_integrity

| ID | Rule | Level | Automation |
|---|---|---|---|
| ARCH-018 | No setters that permit invalid aggregate/entity state | SHOULD | partial |
| ARCH-019 | Internal aggregate collections are not exposed mutable | SHOULD | partial |
| ARCH-020 | Inter-aggregate references are by ID, not object | SHOULD | partial |
| ARCH-021 | One transaction modifies one aggregate (UoW boundary) | MUST* | partial |
| ARCH-022 | Repositories operate at root level and return aggregates, not rows/DTOs | MUST | partial |
| ARCH-023 | Domain events are immutable and past-tense | MUST | full |
| ARCH-028 | No Active Record | MUST | partial |
| ARCH-031 | Value Objects are immutable and validate on construction | MUST | partial |
| ARCH-032 | The domain raises only exceptions derived from commons DomainError | SHOULD | partial |
| ARCH-033 | Every use-case write goes through a Unit of Work | MUST | partial |
| ARCH-051 | Repositories are not query interfaces | MUST | partial |

### application

| ID | Rule | Level | Automation |
|---|---|---|---|
| ARCH-024 | When published, integration events have a versioned schema at the context root | MUST* | manual |
| ARCH-025 | Cross-context communication is through a declared contract, never imports | MUST | partial |
| ARCH-026 | External-provider dependencies sit behind a port | SHOULD | partial |
| ARCH-027 | The domain does not cross the application boundary | SHOULD | manual |
| ARCH-029 | Use cases express intent, not generic CRUD | SHOULD | manual |
| ARCH-030 | One general application service class per context by default | SHOULD | partial |
| ARCH-036 | Integration events are published via transactional outbox when a guarantee is required | MUST* | manual |
| ARCH-042 | Port placement follows the three-homes rule | SHOULD | manual |
| ARCH-045 | A context depends only on consumer-driven contracts it declares | MUST | manual |

### testing

| ID | Rule | Level | Automation |
|---|---|---|---|
| ARCH-038 | Domain objects are never mocked | SHOULD | partial |
| ARCH-039 | In-memory fakes share the contract test with the real adapter | SHOULD | manual |
| ARCH-040 | Test names follow given_<state>__when_<action>__then_<result> | SHOULD | full |

### progressive_structure

| ID | Rule | Level | Automation |
|---|---|---|---|
| ARCH-041 | A module is promoted to a package only past the Section 15 thresholds | MAY | partial |

### cross_cutting

| ID | Rule | Level | Automation |
|---|---|---|---|
| ARCH-043 | Every published message uses the commons event envelope | MUST* | partial |
| ARCH-044 | Every integration event has a published schema in the events catalog | MUST* | partial |
| ARCH-053 | The core does not log | MUST | full |

### structure

| ID | Rule | Level | Automation |
|---|---|---|---|
| ARCH-046 | Aggregate module isolation | MUST | full |
| ARCH-047 | Context shared area is strictly limited | MUST | partial |
| ARCH-048 | No context-level application package | MUST | full |
| ARCH-049 | One aggregate root per aggregate module | MUST | partial |
| ARCH-050 | Declared context dependency graph | MUST | full |
| ARCH-052 | Read layer does not import the write side | MUST | full |
| ARCH-054 | Domain services for an aggregate live in a services/ directory | SHOULD | partial |
| ARCH-055 | Every Python package directory has an __init__.py | SHOULD | full |

### Rule reference

#### ARCH-001 — Domain does not depend on adapters
- **Level:** MUST · **Automation:** full · **Tier:** core · **Category:** dependencies
- **Validation:** `import-linter` — layered contract; domain is the innermost layer
- **Description:** No module under a context's domain/ package may import from that context's adapters/ package or from commons/adapters/.
- **Rationale:** Inverting this dependency (DIP) lets the core be tested without a database and lets the store be swapped without touching business rules.
- **Correct:**
  ```
  # sales/orders/domain/model/ports.py
  class OrderRepository(Protocol):
      def get(self, order_id: OrderId) -> Order: ...
  ```
- **Incorrect:**
  ```
  # sales/orders/domain/model/aggregate.py
  from sales.orders.adapters.postgres_order_repository import PostgresOrderRepository
  ```
- **Related:** ARCH-008

#### ARCH-002 — Domain does not depend on application
- **Level:** MUST · **Automation:** full · **Tier:** core · **Category:** dependencies
- **Validation:** `import-linter` — layered contract
- **Description:** No module under a context's domain/ package imports from that context's application/ package.
- **Rationale:** The domain is the innermost layer; use-case orchestration depends on it, never the reverse.
- **Correct:**
  ```
  # sales/orders/application/order.py
  from sales.orders.domain.model.aggregate import Order
  ```
- **Incorrect:**
  ```
  # sales/orders/domain/model/aggregate.py
  from sales.orders.application.order_service import OrderService
  ```

#### ARCH-003 — Domain does not depend on frameworks
- **Level:** MUST · **Automation:** full · **Tier:** core · **Category:** dependencies
- **Validation:** `import-linter` — forbidden contract; domain -/-> (pydantic, sqlalchemy, fastapi, ...)
- **Description:** No module under a context's domain/ package imports a web framework, an ORM, a DI container, or pydantic.
- **Rationale:** A framework-free domain stays unit-testable without a runtime and keeps vendor choices out of the business core.
- **Correct:**
  ```
  # sales/orders/domain/model/aggregate.py
  from dataclasses import dataclass
  from commons.types.ids import EntityId
  ```
- **Incorrect:**
  ```
  # sales/orders/domain/model/aggregate.py
  from pydantic import BaseModel
  from sqlalchemy.orm import Mapped
  ```

#### ARCH-004 — Domain performs no I/O
- **Level:** MUST · **Automation:** partial · **Tier:** full · **Category:** dependencies
- **Validation:** `ruff` — flake8-tidy-imports banned-api (datetime.now, uuid4, open, socket) in domain/
- **Description:** No module under a context's domain/ package calls the wall clock, a random source, the network, or the disk; time and identity arrive through the Clock and IdGenerator ports.
- **Rationale:** A domain that reads datetime.now() or a socket is non-deterministic and cannot be tested in microseconds.
- **Correct:**
  ```
  # sales/orders/domain/model/aggregate.py
  @classmethod
  def place(cls, clock: Clock, ids: IdGenerator) -> "Order":
      return cls(id=ids.next_identity(), placed_at=clock.now())
  ```
- **Incorrect:**
  ```
  # sales/orders/domain/model/aggregate.py
  from datetime import datetime
  placed_at = datetime.now()
  ```

#### ARCH-005 — Application does not depend on adapters
- **Level:** MUST · **Automation:** full · **Tier:** core · **Category:** dependencies
- **Validation:** `import-linter` — layered contract
- **Description:** No module under a context's application/ package imports from that context's adapters/ package or from commons/adapters/.
- **Rationale:** Orchestration names ports only; the concrete adapter is injected from providers.py and is never imported by the use case.
- **Correct:**
  ```
  # sales/orders/application/order.py
  def __init__(self, orders: OrderRepository, uow: UnitOfWork) -> None: ...
  ```
- **Incorrect:**
  ```
  # sales/orders/application/order.py
  from sales.orders.adapters.order_repository import SqlAlchemyOrderRepository
  ```

#### ARCH-006 — Application does not depend on entrypoints
- **Level:** MUST · **Automation:** full · **Tier:** core · **Category:** dependencies
- **Validation:** `import-linter` — layered contract
- **Description:** No module under a context's application/ package imports from that context's entrypoints/ package.
- **Rationale:** Entrypoints are inbound adapters that call the application; the dependency arrow never points back out to transport code.
- **Correct:**
  ```
  # sales/entrypoints/http.py
  from sales.orders.application.order_service import OrderService
  ```
- **Incorrect:**
  ```
  # sales/orders/application/order.py
  from sales.entrypoints.http import parse_body
  ```

#### ARCH-007 — Application does not construct concrete adapters
- **Level:** MUST · **Automation:** partial · **Tier:** full · **Category:** dependencies
- **Validation:** `grimp` — import-graph assert; catches adapter classes imported from the adapters/ package, not an adapter class defined and instantiated within application/ itself
- **Description:** No module under a context's application/ package instantiates an adapter class such as SqlAlchemyOrderRepository(...) or HttpCreditGateway(...).
- **Rationale:** Constructing an adapter couples the use case to one technology choice and defeats dependency injection.
- **Correct:**
  ```
  # sales/entrypoints/providers.py
  orders = SqlAlchemyOrderRepository(uow)
  return OrderService(uow=uow, orders=orders)
  ```
- **Incorrect:**
  ```
  # sales/orders/application/order.py
  self._orders = SqlAlchemyOrderRepository(SqlAlchemyUnitOfWork())
  ```
- **Related:** ARCH-005

#### ARCH-008 — Adapters implement ports; the core imports abstractions only
- **Level:** MUST · **Automation:** partial · **Tier:** core · **Category:** dependencies
- **Validation:** `import-linter` — layered contract (import half); Protocol conformance of adapters is reviewed at PR time
- **Description:** Every concrete adapter in a context's adapters/ package implements a Protocol declared in domain/model/ports.py or a colocated application Protocol; domain/ and application/ import only those abstractions.
- **Rationale:** The core names the contract it needs and adapters plug in behind it, so the store can be replaced without editing business rules.
- **Correct:**
  ```
  # sales/orders/adapters/order_repository.py
  class SqlAlchemyOrderRepository:  # implements OrderRepository (domain port)
      def get(self, order_id: OrderId) -> Order: ...
  ```
- **Incorrect:**
  ```
  # sales/orders/domain/services/service.py
  from sales.orders.adapters.order_repository import SqlAlchemyOrderRepository
  ```
- **Related:** ARCH-001, ARCH-042

#### ARCH-009 — Entrypoints obtain wired services from providers; never construct or call outbound adapters directly
- **Level:** MUST · **Automation:** partial · **Tier:** full · **Category:** dependencies
- **Validation:** `import-linter` — forbidden contract (import half); entrypoints calling persistence/session/http-client directly is a runtime fact the import graph cannot see
- **Description:** No module under a context's entrypoints/ package constructs an outbound adapter or calls persistence, sessions, or HTTP clients directly; it obtains a fully wired service from providers.py and calls only that service.
- **Rationale:** An entrypoint that news up a repository or calls session.execute is untestable without transport and leaks wiring across the boundary.
- **Correct:**
  ```
  # sales/entrypoints/http.py
  service = providers.order_service()
  service.create_order(command)
  ```
- **Incorrect:**
  ```
  # sales/entrypoints/http.py
  repo = SqlAlchemyOrderRepository(SqlAlchemyUnitOfWork())
  repo.save(order)
  ```
- **Related:** ARCH-037

#### ARCH-010 — Entrypoints contain no business logic
- **Level:** SHOULD · **Automation:** partial · **Tier:** full · **Category:** dependencies
- **Validation:** `review` — PR checklist; does the handler decide anything about business meaning?
- **Description:** A module under a context's entrypoints/ package does not branch on business meaning; it translates the stimulus into a command, calls one service method, and maps the result or exception back to the transport.
- **Rationale:** Business rules in a controller are hidden from domain tests and cannot be reused by another entrypoint.
- **Correct:**
  ```
  # sales/entrypoints/http.py
  cmd = CreateOrder(customer_id=body.customer_id, lines=body.lines)
  return _to_response(service.create_order(cmd))
  ```
- **Incorrect:**
  ```
  # sales/entrypoints/http.py
  if order.total > customer.credit_limit:
      raise HTTPException(402)
  ```

#### ARCH-011 — Entrypoints call application services, not other entrypoints
- **Level:** MUST · **Automation:** full · **Tier:** full · **Category:** dependencies
- **Validation:** `import-linter` — forbidden contract; entrypoints/*.py -/-> entrypoints/*.py except providers
- **Description:** No module under a context's entrypoints/ package imports or calls another entrypoint module (providers.py aside).
- **Rationale:** Chaining entrypoints hides a use case behind transport translation and duplicates orchestration.
- **Correct:**
  ```
  # sales/entrypoints/cli.py
  from sales.entrypoints import providers
  providers.order_service().create_order(cmd)
  ```
- **Incorrect:**
  ```
  # sales/entrypoints/cli.py
  from sales.entrypoints.http import create_order_handler
  ```

#### ARCH-012 — A context imports nothing from another context
- **Level:** MUST · **Automation:** full · **Tier:** core · **Category:** dependencies
- **Validation:** `import-linter` — independence contract
- **Description:** A bounded context imports nothing from another bounded context (its domain/, application/, or adapters/ packages).
- **Rationale:** Keeps contexts substitutable and independently deployable; a change inside one context cannot break another; the contract between teams stays explicit.
- **Correct:**
  ```
  # sales needs a credit check
  # sales/orders/domain/model/ports.py declares CreditCheckPort (consumer-driven)
  # bootstrap/ wires an adapter backed by billing's application service
  ```
- **Incorrect:**
  ```
  from billing.invoices.domain.model.aggregate import Invoice   # in sales/orders/
  ```
- **Related:** ARCH-013, ARCH-025, ARCH-045

#### ARCH-013 — No dependency cycles between contexts
- **Level:** SHOULD · **Automation:** full · **Tier:** full · **Category:** dependencies
- **Validation:** `grimp` — import-graph cycle detection across top-level context packages
- **Description:** The import graph over the top-level context packages is acyclic; no two contexts import each other, directly or transitively.
- **Rationale:** A cycle fuses two contexts into one unit that cannot be reasoned about, tested, or extracted separately.
- **Correct:**
  ```
  # sales declares a consumer-driven port; bootstrap wires a billing adapter
  # billing does not import sales
  ```
- **Incorrect:**
  ```
  # sales/orders/adapters/credit_gateway.py imports billing.invoices.application...
  # billing/invoices/adapters/order_gateway.py imports sales.orders.application...
  ```
- **Related:** ARCH-012

#### ARCH-014 — shared_kernel imports nothing from any context
- **Level:** MUST · **Automation:** full · **Tier:** full · **Category:** dependencies
- **Validation:** `import-linter` — forbidden contract; shared_kernel -/-> contexts
- **Description:** No module under shared_kernel/ imports from any src/<context> package.
- **Rationale:** The shared kernel is upstream of every context; importing a context would invert the governance direction and couple all consumers.
- **Correct:**
  ```
  # shared_kernel/money.py
  from commons.types.errors import DomainError
  ```
- **Incorrect:**
  ```
  # shared_kernel/pricing.py
  from sales.orders.domain.model.aggregate import Order
  ```

#### ARCH-015 — commons/types imports nothing from contexts, application, adapters, or shared_kernel
- **Level:** MUST · **Automation:** full · **Tier:** full · **Category:** dependencies
- **Validation:** `import-linter` — forbidden contract; commons.types -/-> everything above it
- **Description:** No module under commons/types/ imports from any context package, from any application/ or adapters/ package, or from shared_kernel/.
- **Rationale:** commons/types is the dependency-free base importable by everyone including domain/; any upward import would create a cycle.
- **Correct:**
  ```
  # commons/types/clock.py
  from typing import Protocol
  ```
- **Incorrect:**
  ```
  # commons/types/ids.py
  from sales.orders.domain.model.aggregate import OrderId
  ```
- **Related:** ARCH-035

#### ARCH-016 — commons/types contains no business logic
- **Level:** MUST · **Automation:** manual · **Tier:** full · **Category:** dependencies
- **Validation:** `review` — PR checklist; would you mention this when describing the business?
- **Description:** Modules under commons/types/ hold only dependency-free technical primitives and Protocols, with no rule a business person would recognise.
- **Rationale:** A business policy hidden in commons/types is invisible to the owning context and silently shared with every other one.
- **Correct:**
  ```
  # commons/types/pagination.py
  @dataclass(frozen=True)
  class Page:
      items: tuple[object, ...]
      total: int
  ```
- **Incorrect:**
  ```
  # commons/types/pricing.py
  VAT_RATE = Decimal("0.21")  # a tax rule belongs to a context or shared_kernel
  ```

#### ARCH-017 — Nothing imports bootstrap
- **Level:** MUST · **Automation:** full · **Tier:** full · **Category:** dependencies
- **Validation:** `import-linter` — forbidden contract; * -/-> bootstrap (allow main.py)
- **Description:** No module outside bootstrap/ imports from bootstrap/, with main.py the only exception.
- **Rationale:** bootstrap/ is the composition root; importing it from a context pulls wiring and config into business code and creates a god-module dependency.
- **Correct:**
  ```
  # main.py
  from bootstrap.container import build_container
  ```
- **Incorrect:**
  ```
  # sales/orders/application/order.py
  from bootstrap.container import build_container
  ```

#### ARCH-018 — No setters that permit invalid aggregate/entity state
- **Level:** SHOULD · **Automation:** partial · **Tier:** full · **Category:** model_integrity
- **Validation:** `ast-checker` — flag public setters or assignable public attributes on domain model classes
- **Description:** Aggregate and entity classes expose no public attribute setter or property setter that can move the object into a state violating its invariants; mutation happens only through business-named methods that validate.
- **Rationale:** Setter-driven aggregates allow illegal transitions and bypass the invariant checks that intention-revealing methods enforce.
- **Correct:**
  ```
  class Order:
      def add_line(self, line: OrderLine) -> None:
          self._guard_not_shipped()
          self._lines.append(line)
  ```
- **Incorrect:**
  ```
  class Order:
      @status.setter
      def status(self, value: str) -> None:
          self._status = value
  ```
- **Related:** ARCH-031

#### ARCH-019 — Internal aggregate collections are not exposed mutable
- **Level:** SHOULD · **Automation:** partial · **Tier:** full · **Category:** model_integrity
- **Validation:** `ast-checker` — flag accessors returning a bare internal mutable container
- **Description:** A property or accessor on an aggregate that surfaces an internal list, dict, or set returns a copy or an immutable view, never the backing collection.
- **Rationale:** Handing out the live collection lets callers mutate aggregate state without passing through invariant-checking methods.
- **Correct:**
  ```
  class Order:
      @property
      def lines(self) -> tuple[OrderLine, ...]:
          return tuple(self._lines)
  ```
- **Incorrect:**
  ```
  class Order:
      @property
      def lines(self) -> list[OrderLine]:
          return self._lines
  ```

#### ARCH-020 — Inter-aggregate references are by ID, not object
- **Level:** SHOULD · **Automation:** partial · **Tier:** full · **Category:** model_integrity
- **Validation:** `review` — PR checklist; does any aggregate field hold another aggregate instance?
- **Description:** An aggregate root holds another aggregate's identifier (for example CustomerId), not a reference to the other aggregate instance.
- **Rationale:** Object references across aggregates build large graphs, blur the consistency boundary, and make the context hard to extract.
- **Correct:**
  ```
  @dataclass
  class Order:
      customer_id: CustomerId
  ```
- **Incorrect:**
  ```
  @dataclass
  class Order:
      customer: Customer
  ```

#### ARCH-021 — One transaction modifies one aggregate (UoW boundary)
- **Level:** MUST* · **Automation:** partial · **Tier:** full · **Category:** model_integrity
- **Validation:** `review` — PR checklist plus ADR waiver expiry check over docs/adr/
- **Description:** A single unit-of-work block loads and mutates exactly one aggregate instance; touching a second aggregate in the same transaction requires a documented ADR justification.
- **Rationale:** One aggregate per transaction keeps the Unit of Work portable to stores without multi-item transactions and keeps the extraction path open.
- **Correct:**
  ```
  with uow:
      order = orders.get(order_id)
      order.cancel()
      uow.commit()
  ```
- **Incorrect:**
  ```
  with uow:
      order.cancel()
      invoice.void()          # second aggregate, same transaction
      uow.commit()
  ```
- **Related:** ARCH-033

#### ARCH-022 — Repositories operate at root level and return aggregates, not rows/DTOs
- **Level:** MUST · **Automation:** partial · **Tier:** full · **Category:** model_integrity
- **Validation:** `review` — PR checklist; do repo methods return aggregates and stay at root level?
- **Description:** Repository port methods are named at aggregate-root level (get, add, save, next_identity, specification queries) and return aggregate instances, never ORM rows, tuples, or DTOs, and never a find_x_with_y() -> DTO business query.
- **Rationale:** A repository that returns rows or answers business questions leaks persistence and grows into an unbounded business service.
- **Correct:**
  ```
  class OrderRepository(Protocol):
      def get(self, order_id: OrderId) -> Order: ...
      def add(self, order: Order) -> None: ...
  ```
- **Incorrect:**
  ```
  class OrderRepository(Protocol):
      def find_orders_with_overdue_invoices(self) -> list[OrderRow]: ...
  ```
- **Related:** ARCH-029

#### ARCH-023 — Domain events are immutable and past-tense
- **Level:** MUST · **Automation:** full · **Tier:** core · **Category:** model_integrity
- **Validation:** `ast-checker` — frozen dataclass plus past-tense name regex
- **Description:** Every class defined in a context's domain/model/events.py is a frozen dataclass and is named in the past tense (e.g. OrderPlaced).
- **Rationale:** A past fact does not change, so the object is immutable; the past-tense name signals it is a fact, not a command.
- **Correct:**
  ```
  @dataclass(frozen=True)
  class OrderPlaced:
      order_id: OrderId
      occurred_at: datetime
  ```
- **Incorrect:**
  ```
  class PlaceOrderEvent:
      def apply(self) -> None: ...
  ```

#### ARCH-024 — When published, integration events have a versioned schema at the context root
- **Level:** MUST* · **Automation:** manual · **Tier:** full · **Category:** application
- **Validation:** `review` — PR checklist; "starts being consumed" is a judgment about intent, not an import/AST fact
- **Description:** A context does not publish integration events by default. When it starts being consumed by another context, the promoted event moves out of its aggregate module's domain/model/events.py into a dedicated <context>/integration_events.py with an explicit version field, and its wire schema is exported to the events catalog; consumers never import the event class.
- **Rationale:** Integration events are a cross-team contract; expressed as importable classes they would couple producer and consumer lifecycles. There is no context-level application/ package (ARCH-048), so the promoted module lives at the context root, not under any aggregate module.
- **Correct:**
  ```
  # sales/integration_events.py
  @dataclass(frozen=True)
  class OrderPlacedV1:
      event_version: int = 1
      order_id: str = ""
  ```
- **Incorrect:**
  ```
  # billing/invoices/application/consume.py
  from sales.orders.domain.model.events import OrderPlaced
  ```
- **Related:** ARCH-025, ARCH-044

#### ARCH-025 — Cross-context communication is through a declared contract, never imports
- **Level:** MUST · **Automation:** partial · **Tier:** full · **Category:** application
- **Validation:** `import-linter` — independence contract (import half); declared contract/ACL presence on the other side is reviewed at PR time
- **Description:** A context reaches another context only through a contract it declares (a consumer-driven port wired in bootstrap/, or a serialized integration event with an ACL), with zero imports between contexts; synchronous by default, asynchronous when the use case tolerates eventual consistency.
- **Rationale:** Contract-mediated communication keeps contexts independently deployable and makes the seam explicit for the teams on each side.
- **Correct:**
  ```
  # sales/orders/domain/model/ports.py
  class CreditCheckPort(Protocol):
      def has_credit(self, customer_id: CustomerId, amount: Money) -> bool: ...
  # bootstrap/ wires an adapter backed by billing's application service
  ```
- **Incorrect:**
  ```
  # sales/orders/application/order.py
  from billing.invoices.application.invoice_service import InvoiceService
  ```
- **Related:** ARCH-012, ARCH-045

#### ARCH-026 — External-provider dependencies sit behind a port
- **Level:** SHOULD · **Automation:** partial · **Tier:** full · **Category:** application
- **Validation:** `review` — PR checklist; is every external provider injected behind a Protocol?
- **Description:** Any dependency on an external provider (email, payment, SMS, third-party API) is used through a Protocol injected into the use case, not by importing the vendor SDK into application/.
- **Rationale:** A port at the integration seam keeps the use case testable with a fake and lets the provider be swapped without touching orchestration.
- **Correct:**
  ```
  class PaymentGateway(Protocol):
      def charge(self, customer_id: CustomerId, amount: Money) -> ChargeId: ...
  ```
- **Incorrect:**
  ```
  # sales/orders/application/order.py
  import stripe
  stripe.Charge.create(amount=total, currency="eur")
  ```
- **Related:** ARCH-042

#### ARCH-027 — The domain does not cross the application boundary
- **Level:** SHOULD · **Automation:** manual · **Tier:** full · **Category:** application
- **Validation:** `review` — PR checklist; does any service method return a domain type?
- **Description:** An application service method returns a DTO or a primitive, never an aggregate, entity, or domain value object; the mapping happens in the application layer.
- **Rationale:** Returning the aggregate couples the transport and its callers to the internal model, so the model can no longer change freely.
- **Correct:**
  ```
  def get_order(self, query: GetOrder) -> OrderView:
      order = self._orders.get(query.order_id)
      return OrderView(id=str(order.id), total=str(order.total))
  ```
- **Incorrect:**
  ```
  def get_order(self, query: GetOrder) -> Order:
      return self._orders.get(query.order_id)
  ```

#### ARCH-028 — No Active Record
- **Level:** MUST · **Automation:** partial · **Tier:** full · **Category:** model_integrity
- **Validation:** `ruff` — banned-api; no ORM base or import in domain/, plus ast check for save/delete on model classes
- **Description:** An aggregate class has no persistence base class, ORM decorator, or ORM import and no save()/delete() method; translation between the aggregate and its stored form lives entirely in adapters/.
- **Rationale:** An Active Record aggregate entangles invariants with the database and cannot be unit-tested without it.
- **Correct:**
  ```
  # sales/orders/domain/model/aggregate.py
  @dataclass
  class Order: ...
  # sales/orders/adapters/mapping.py
  map_imperatively(Order, order_table)
  ```
- **Incorrect:**
  ```
  # sales/orders/domain/model/aggregate.py
  class Order(Base):
      __tablename__ = "orders"
      def save(self) -> None: self._session.add(self)
  ```
- **Related:** ARCH-001, ARCH-033

#### ARCH-029 — Use cases express intent, not generic CRUD
- **Level:** SHOULD · **Automation:** manual · **Tier:** full · **Category:** application
- **Validation:** `review` — PR checklist; does the method name a business action?
- **Description:** Application service methods are named for the business action (place_order, cancel_order, add_item) and carry an intent-revealing command, not create/update/delete over a data shape.
- **Rationale:** CRUD method names hide the business intent, so invariants cannot be verified per change.
- **Correct:**
  ```
  def cancel_order(self, command: CancelOrder) -> None: ...
  def ship_order(self, command: ShipOrder) -> None: ...
  ```
- **Incorrect:**
  ```
  def update_order(self, order_id: str, fields: dict) -> None: ...
  ```
- **Related:** ARCH-022

#### ARCH-030 — One general application service class per context by default
- **Level:** SHOULD · **Automation:** partial · **Tier:** full · **Category:** application
- **Validation:** `ast-checker` — service size warning at ~7 methods / ~200 lines / 5 constructor params
- **Description:** A context has one application service class by default with one public method per use case; the checker warns (does not fail) past about 7 public methods, 200 lines, or 5 constructor parameters and adds a review-checklist item.
- **Rationale:** A single general service is simpler than pre-split capability services; splitting is mechanical and only pays off once cohesion actually drops.
- **Correct:**
  ```
  class OrderService:
      def create_order(self, c: CreateOrder) -> OrderId: ...
      def cancel_order(self, c: CancelOrder) -> None: ...
      def add_item(self, c: AddItemToOrder) -> None: ...
  ```
- **Incorrect:**
  ```
  class OrderService:   # 14 methods, 9 constructor deps, 600 lines, never split
      ...
  ```

#### ARCH-031 — Value Objects are immutable and validate on construction
- **Level:** MUST · **Automation:** partial · **Tier:** core · **Category:** model_integrity
- **Validation:** `ast-checker` — value_objects.py classes must be frozen dataclasses with __post_init__
- **Description:** Every value object class is a frozen dataclass with no setters, validates its invariants in __post_init__, and returns new instances from its methods rather than mutating self.
- **Rationale:** A value object is defined by its values; mutability or unvalidated construction lets invalid values propagate through the model.
- **Correct:**
  ```
  @dataclass(frozen=True)
  class Money:
      amount: Decimal
      currency: str
      def __post_init__(self) -> None:
          if self.amount.as_tuple().exponent < -2:
              raise InvalidMoney(self.amount)
  ```
- **Incorrect:**
  ```
  class Money:
      def __init__(self, amount: Decimal, currency: str) -> None:
          self.amount = amount
      def add(self, other: "Money") -> None:
          self.amount += other.amount
  ```
- **Related:** ARCH-018

#### ARCH-032 — The domain raises only exceptions derived from commons DomainError
- **Level:** SHOULD · **Automation:** partial · **Tier:** full · **Category:** model_integrity
- **Validation:** `review` — PR checklist plus ast scan for raise of non-DomainError types in domain/
- **Description:** Code under domain/ raises only exception types defined in domain/model/exceptions.py, each subclassing commons.types.errors.DomainError, never a bare ValueError, KeyError, or library exception.
- **Rationale:** A consistent domain exception hierarchy lets the application and entrypoints map failures predictably and keeps library exceptions from carrying business meaning.
- **Correct:**
  ```
  # sales/orders/domain/model/exceptions.py
  class OrderAlreadyShipped(DomainError): ...
  # sales/orders/domain/model/aggregate.py
  raise OrderAlreadyShipped(self.id)
  ```
- **Incorrect:**
  ```
  # sales/orders/domain/model/aggregate.py
  raise ValueError("order already shipped")
  ```

#### ARCH-033 — Every use-case write goes through a Unit of Work
- **Level:** MUST · **Automation:** partial · **Tier:** core · **Category:** model_integrity
- **Validation:** `ast-checker` — state-changing service methods must contain a `with uow:` and uow.commit()
- **Description:** Every application service method that changes state opens a UnitOfWork block and commits through it; the service never calls commit on a repository or a session directly.
- **Rationale:** A single transaction boundary per use case is also the point where domain events are collected for publication.
- **Correct:**
  ```
  def cancel_order(self, command: CancelOrder) -> None:
      with self._uow:
          order = self._orders.get(command.order_id)
          order.cancel()
          self._uow.commit()
  ```
- **Incorrect:**
  ```
  def cancel_order(self, command: CancelOrder) -> None:
      order = self._orders.get(command.order_id)
      order.cancel()
      self._orders.session.commit()
  ```
- **Related:** ARCH-021

#### ARCH-034 — commons/adapters is not imported by domain or application
- **Level:** MUST · **Automation:** full · **Tier:** full · **Category:** dependencies
- **Validation:** `import-linter` — forbidden contract; domain|application -/-> commons.adapters
- **Description:** No module under any context's domain/ or application/ package imports from commons/adapters/.
- **Rationale:** commons/adapters holds framework-bound implementations; only adapters/, entrypoints/, bootstrap/, and tests may touch them.
- **Correct:**
  ```
  # sales/orders/adapters/unit_of_work.py
  from commons.adapters.unit_of_work import SqlAlchemyUnitOfWork
  ```
- **Incorrect:**
  ```
  # sales/orders/application/order.py
  from commons.adapters.unit_of_work import SqlAlchemyUnitOfWork
  ```

#### ARCH-035 — commons/types does not import any framework
- **Level:** MUST · **Automation:** full · **Tier:** full · **Category:** dependencies
- **Validation:** `import-linter` — forbidden contract; commons.types -/-> (sqlalchemy, fastapi, pydantic, ...)
- **Description:** No module under commons/types/ imports a web framework, an ORM, a DI container, pydantic, or any other third-party runtime library.
- **Rationale:** commons/types must stay importable with zero third-party dependencies so the domain that depends on it stays pure.
- **Correct:**
  ```
  # commons/types/event_bus.py
  from typing import Iterable, Protocol
  ```
- **Incorrect:**
  ```
  # commons/types/unit_of_work.py
  from sqlalchemy.orm import Session
  ```
- **Related:** ARCH-015

#### ARCH-036 — Integration events are published via transactional outbox when a guarantee is required
- **Level:** MUST* · **Automation:** manual · **Tier:** full · **Category:** application
- **Validation:** `review` — PR checklist plus ADR check; applies only when a delivery guarantee is declared
- **Description:** When a use case requires a delivery or transactional side-effect guarantee, its integration events are written to the outbox table in the same transaction as the state change and published by a separate process; publish-after-commit is allowed only when no such guarantee is required.
- **Rationale:** Publishing after commit can lose events if the process dies; the outbox makes the event durable together with the state change.
- **Correct:**
  ```
  with uow:
      self._orders.add(order)
      self._outbox.add(OrderPlacedV1(order_id=str(order.id)))
      uow.commit()
  ```
- **Incorrect:**
  ```
  with uow:
      self._orders.add(order)
      uow.commit()
  self._bus.publish(OrderPlacedV1(order_id=str(order.id)))  # lost on crash here
  ```
- **Related:** ARCH-043

#### ARCH-037 — Entrypoint wiring is defined in per-context providers.py, backed by bootstrap
- **Level:** MUST · **Automation:** partial · **Tier:** full · **Category:** dependencies
- **Validation:** `ast-checker` — providers.py present per context; entrypoints import wired services only from it
- **Description:** Each context exposes its wired services through entrypoints/providers.py, which pulls singletons and factories from the bootstrap/ container; entrypoints import services only from providers.py.
- **Rationale:** One per-context wiring seam keeps construction out of handlers and gives the composition root a single place to assemble each service.
- **Correct:**
  ```
  # sales/entrypoints/providers.py
  def order_service() -> OrderService:
      uow = unit_of_work()
      return OrderService(uow=uow, orders=SqlAlchemyOrderRepository(uow), bus=event_bus())
  ```
- **Incorrect:**
  ```
  # sales/entrypoints/http.py
  order_service = OrderService(uow=SqlAlchemyUnitOfWork(), orders=..., bus=...)
  ```
- **Related:** ARCH-009

#### ARCH-038 — Domain objects are never mocked
- **Level:** SHOULD · **Automation:** partial · **Tier:** full · **Category:** testing
- **Validation:** `review` — PR checklist plus grep for Mock(spec=<domain type>) in tests
- **Description:** Tests never replace an aggregate, entity, domain value object, domain service, or shared_kernel value object with a mock or stub; they exercise the real object.
- **Rationale:** Mocking the domain couples tests to its implementation and stops them verifying the real invariants.
- **Correct:**
  ```
  order = Order.place(customer_id, lines)     # real aggregate
  order.add_item(item)
  assert order.total == Money(Decimal("30.00"), "EUR")
  ```
- **Incorrect:**
  ```
  order = Mock(spec=Order)
  order.total = Money(Decimal("30.00"), "EUR")
  ```
- **Related:** ARCH-039

#### ARCH-039 — In-memory fakes share the contract test with the real adapter
- **Level:** SHOULD · **Automation:** manual · **Tier:** full · **Category:** testing
- **Validation:** `review` — PR checklist; is the fake bound to the shared contract test?
- **Description:** Each in-memory fake (repository, event bus, clock) is exercised by the same contract test as the real adapter, and the repository contract test asserts that domain events surface in uow.collect_new_events() after add/get.
- **Rationale:** A fake not held to the real adapter's contract can silently diverge, for instance a custom UnitOfWork that forgets track() and drops events.
- **Correct:**
  ```
  @pytest.mark.parametrize("repo", ["in_memory", "sqlalchemy"])
  def given_added_order__when_get__then_events_surface_in_collect_new_events(repo):
      ...
  ```
- **Incorrect:**
  ```
  # InMemoryOrderRepository has its own ad hoc test; the real repo test is unrelated
  ```

#### ARCH-040 — Test names follow given_<state>__when_<action>__then_<result>
- **Level:** SHOULD · **Automation:** full · **Tier:** full · **Category:** testing
- **Validation:** `ast-checker` — regex over test function names; ^given_.+__when_.+__then_.+$
- **Description:** Every test function name matches given_<state>__when_<action>__then_<result>, with double underscores separating the three parts.
- **Rationale:** A uniform three-part name states the scenario and the expectation without reading the body and keeps the suite to one test per rule.
- **Correct:**
  ```
  def given_shipped_order__when_add_item__then_raises_order_already_shipped():
      ...
  ```
- **Incorrect:**
  ```
  def test_add_item_fails():
      ...
  ```

#### ARCH-041 — A module is promoted to a package only past the Section 15 thresholds
- **Level:** MAY · **Automation:** partial · **Tier:** full · **Category:** progressive_structure
- **Validation:** `ast-checker` — promotion thresholds check (line count, aggregate count, port count)
- **Description:** A flat module (domain/model.py, application/<capability>.py, adapters/<adapter>.py) is split into a package only once it crosses a Section 15 threshold, for example domain/model.py past about 400 lines or 2 aggregates.
- **Rationale:** Structure should grow when it hurts, not before; promoting a module early adds indirection with no payoff.
- **Correct:**
  ```
  # domain/model.py at 180 lines, one aggregate -> stays a single module
  ```
- **Incorrect:**
  ```
  # domain/model/ split into aggregates/, value_objects/, events/ on day one,
  # each folder holding a single 20-line file
  ```

#### ARCH-042 — Port placement follows the three-homes rule
- **Level:** SHOULD · **Automation:** manual · **Tier:** full · **Category:** application
- **Validation:** `review` — PR checklist; "shared across use-case modules" and the 3+ threshold need cross-module usage analysis, not an AST fact
- **Description:** A Protocol is placed by the three-homes rule (generic technical Protocols in commons/types/, domain-vocabulary contracts in domain/model/ports.py, non-domain outbound contracts colocated in the use-case module), and there is no application/ports.py until a context has 3+ application ports shared across use-case modules.
- **Rationale:** Keeping domain/model/ports.py a faithful list of domain concepts keeps integration-contract churn out of the stable domain file.
- **Correct:**
  ```
  # commons/types/clock.py                    -> Clock
  # sales/orders/domain/model/ports.py        -> OrderRepository
  # sales/orders/application/order.py -> class OrderNotifier(Protocol): ...
  ```
- **Incorrect:**
  ```
  # sales/orders/application/ports.py -> EmailSender, Clock, OrderRepository (one dumping file)
  ```
- **Related:** ARCH-008, ARCH-026

#### ARCH-043 — Every published message uses the commons event envelope
- **Level:** MUST* · **Automation:** partial · **Tier:** full · **Category:** cross_cutting
- **Validation:** `ast-checker` — publish call argument must be an EventEnvelope with the six required fields
- **Description:** Every published integration message is wrapped in the commons/ EventEnvelope carrying correlation_id, causation_id, occurred_at, event_type, event_version, and payload, and the correlation id is read from the contextvar set by the entrypoint.
- **Rationale:** A uniform envelope with a correlation id on a contextvar is what makes an asynchronous flow traceable through a broker.
- **Correct:**
  ```
  envelope = EventEnvelope.wrap(OrderPlacedV1(order_id=str(order.id)))
  bus.publish(envelope)
  ```
- **Incorrect:**
  ```
  bus.publish({"order_id": str(order.id)})   # no envelope, no correlation id
  ```
- **Related:** ARCH-036, ARCH-044

#### ARCH-044 — Every integration event has a published schema in the events catalog
- **Level:** MUST* · **Automation:** partial · **Tier:** full · **Category:** cross_cutting
- **Validation:** `schema` — every published event has a catalog schema; producer fixtures validate against it
- **Description:** For every integration event a context publishes there is a versioned schema file in the events catalog, and the producer contract test validates each emitted event against it.
- **Rationale:** The published schema is the Published Language, the single artifact producers and consumers agree on, versioned so a change is a new event version rather than an in-place edit.
- **Correct:**
  ```
  # events_catalog/sales/order_placed.v1.json  (JSON Schema)
  # producer test: every emitted OrderPlaced validates against it
  ```
- **Incorrect:**
  ```
  # OrderPlaced is published; no schema file exists; the field set changes in place
  ```
- **Related:** ARCH-024

#### ARCH-045 — A context depends only on consumer-driven contracts it declares
- **Level:** MUST · **Automation:** manual · **Tier:** full · **Category:** application
- **Validation:** `review` — PR checklist; "carries only the fields and operations it uses" is intent, not an AST fact (import half is ARCH-012/025)
- **Description:** For anything a context needs from another context it declares its own narrow port carrying only the fields and operations it uses; it does not consume the other context's full interface or full event shape.
- **Rationale:** Consumer-driven contracts mean removing a field the consumer does not use never breaks it, and the contract documents exactly what the boundary carries.
- **Correct:**
  ```
  # sales/orders/domain/model/ports.py
  class CreditCheckPort(Protocol):
      def has_credit(self, customer_id: CustomerId, amount: Money) -> bool: ...
  ```
- **Incorrect:**
  ```
  # sales/orders/adapters/credit_gateway.py
  from billing.invoices.application.invoice_service import InvoiceService  # calls 8 of 20 methods
  ```
- **Related:** ARCH-012, ARCH-025

#### ARCH-046 — Aggregate module isolation
- **Level:** MUST · **Automation:** full · **Tier:** core · **Category:** structure
- **Validation:** `import-linter` — forbidden contract between sibling modules' application and adapters
- **Description:** An aggregate module does not import another aggregate module's application/ or adapters/ package. References between aggregates are by ID, and those ID types live in the context's shared/ids.py.
- **Rationale:** Aggregate modules are consistency boundaries. Reaching into a sibling's service or repository re-couples them and makes the one-transaction-one-aggregate rule unenforceable.
- **Correct:**
  ```
  # sales/orders/domain/model/aggregate.py
  from sales.shared.ids import UserId
  class Order:
      customer_id: UserId
  ```
- **Incorrect:**
  ```
  # sales/orders/application/order.py
  from sales.users.application.user_service import UserService
  ```
- **Related:** ARCH-020, ARCH-021

#### ARCH-047 — Context shared area is strictly limited
- **Level:** MUST · **Automation:** partial · **Tier:** full · **Category:** structure
- **Validation:** `ast-checker` — no class named *Service/*Repository outside shared/services.py; no aggregate roots; shared/services.py classes must not mutate their own state
- **Description:** <context>/shared/ contains only ID types, policy-free value objects used by two or more aggregates of that context, and domain services spanning them. Those spanning services live specifically in shared/services.py — the one file in shared/ exempt from the *Service/*Repository name-suffix ban, since it is the standard's own documented home for them. Every other file in shared/ keeps the full name-suffix ban, and shared/services.py classes still may not mutate their own state.
- **Rationale:** It is the only context-level code area, so without a narrow admission test it becomes the junk drawer that couples every aggregate module together. Naming the one legitimate exception explicitly (rather than banning *Service outright) keeps the carve-out narrow instead of inviting every file in shared/ to claim it.
- **Correct:**
  ```
  # sales/shared/ids.py
  @dataclass(frozen=True)
  class UserId:
      value: str
  
  # sales/shared/services.py — the documented carve-out
  class PricingService:
      def quote(self, order: Order) -> Money: ...
  ```
- **Incorrect:**
  ```
  # sales/shared/user_service.py — *Service outside services.py is still banned
  class UserService: ...
  
  # sales/shared/services.py — mutation is still banned even here
  class PricingService:
      def bump(self) -> None:
          self.calls += 1
  ```

#### ARCH-048 — No context-level application package
- **Level:** MUST · **Automation:** full · **Tier:** full · **Category:** structure
- **Validation:** `ast-checker` — filesystem check for <context>/application, plus any aggregate-module layer directory still carrying the pre-0.2.0 layer name (infrastructure), which is reported with the rename to adapters
- **Description:** A context has no application/ package of its own. Application services live in aggregate modules, one per aggregate.
- **Rationale:** DDD has no "application service of the context"; application services are per use case and belong with the model they coordinate. A context-level one becomes a coordination layer that hides non-atomic multi-aggregate flow.
- **Correct:**
  ```
  sales/orders/application/order.py
  ```
- **Incorrect:**
  ```
  sales/application/sales_service.py
  ```

#### ARCH-049 — One aggregate root per aggregate module
- **Level:** MUST · **Automation:** partial · **Tier:** full · **Category:** structure
- **Validation:** `ast-checker` — exactly one non-reserved module in domain/model, named aggregate.py
- **Description:** An aggregate module's domain/model/ declares exactly one aggregate root, in aggregate.py.
- **Rationale:** The 1:1 mapping is what makes "where does this go?" answerable without judgement, and a fixed filename means there is no decision to make about what to call it either - the tree looks the same in every module.
- **Correct:**
  ```
  sales/users/domain/model/aggregate.py declaring class User
  ```
- **Incorrect:**
  ```
  sales/users/domain/model/aggregate.py declaring class User and class Order
  ```

#### ARCH-050 — Declared context dependency graph
- **Level:** MUST · **Automation:** full · **Tier:** full · **Category:** structure
- **Validation:** `schema` — parse contexts.toml, topological sort
- **Description:** Every cross-context dependency is declared in contexts.toml, and the declared graph is acyclic.
- **Rationale:** Contexts never import each other, so no import analysis can see a runtime cycle wired through the composition root. Declaring the graph is the only way to check it, and it turns adding an edge into a reviewable diff.
- **Correct:**
  ```
  # contexts.toml
  [contexts.sales]
  depends_on = ["billing"]
  ```
- **Incorrect:**
  ```
  [contexts.sales]
  depends_on = ["billing"]
  [contexts.billing]
  depends_on = ["sales"]
  ```

#### ARCH-051 — Repositories are not query interfaces
- **Level:** MUST · **Automation:** partial · **Tier:** core · **Category:** model_integrity
- **Validation:** `ast-checker` — repository methods returning non-aggregate collections
- **Description:** Repositories persist and retrieve aggregate roots. They are not general-purpose query interfaces: projection-oriented, reporting, search, dashboard, and cross-aggregate reads belong to the context's read/ layer.
- **Rationale:** A repository that grows report queries stops being a collection of roots, drags query pressure into the write model, and starts returning DTOs instead of aggregates.
- **Correct:**
  ```
  class OrderRepository(Protocol):
      def get(self, order_id: OrderId) -> Order: ...
      def add(self, order: Order) -> None: ...
  ```
- **Incorrect:**
  ```
  class OrderRepository(Protocol):
      def find_premium_customers_with_overdue_invoices(self) -> list[ReportRow]: ...
  ```
- **Related:** ARCH-022, ARCH-052

#### ARCH-052 — Read layer does not import the write side
- **Level:** MUST · **Automation:** full · **Tier:** full · **Category:** structure
- **Validation:** `import-linter` — forbidden contract read -> modules' domain/application
- **Description:** <context>/read/ imports no aggregate module's domain/ or application/ package.
- **Rationale:** The read layer exists to answer queries the write model is not shaped for. Importing the write side re-couples them and pulls invariant-carrying objects into query paths.
- **Correct:**
  ```
  # sales/read/customer_overview.py
  @dataclass(frozen=True)
  class CustomerOverview:
      user_id: str
  ```
- **Incorrect:**
  ```
  # sales/read/customer_overview.py
  from sales.users.domain.model.aggregate import User
  ```

#### ARCH-053 — The core does not log
- **Level:** MUST · **Automation:** full · **Tier:** full · **Category:** cross_cutting
- **Validation:** `ruff` — banned logging imports/calls under domain/ and application/
- **Description:** Modules under domain/ and application/ import no logging library and make no logging calls. They raise domain exceptions and emit domain events; entrypoints and outbound adapters log.
- **Rationale:** Logging is an observability concern of the adapters on both sides of the core: entrypoints inbound, adapters/ outbound. Keeping it out of the core keeps the core free of ambient I/O and makes behavior fully assertable from the state and events a use case produces.
- **Correct:**
  ```
  # application: emit a fact
  self._bus.publish_all(self._uow.collect_new_events())
  ```
- **Incorrect:**
  ```
  # application
  import logging
  logging.getLogger(__name__).info("order created")
  ```

#### ARCH-054 — Domain services for an aggregate live in a services/ directory
- **Level:** SHOULD · **Automation:** partial · **Tier:** full · **Category:** structure
- **Validation:** `ast-checker` — domain/services.py must not exist as a file; when domain/services/ has exactly one file, its name must match the aggregate's own name
- **Description:** An aggregate module's domain services live in domain/services/, one file per service - not a single domain/services.py file. A single service is named after the aggregate (order.py for the Order aggregate); 2+ services each get a descriptive name instead. This does not apply to <context>/shared/services.py (ARCH-047), the separate context-level home for services spanning aggregates.
- **Rationale:** A single services.py invites every future domain service for this aggregate to pile into one file. A directory gives each service its own file from the start, the same way domain/model/ already gives each concept its own file, with no restructuring needed when a second service arrives. Naming the lone service after the aggregate (rather than a generic "service") makes it identifiable without opening it, the same reason domain/model/ports.py or events.py are named for what they hold, not for their role alone.
- **Correct:**
  ```
  # sales/orders/domain/services/order.py — file named for the aggregate,
  # since this is the Order module's only domain service
  class PricingCalculator: ...
  ```
- **Incorrect:**
  ```
  # sales/orders/domain/services.py — must be a directory, not a file
  class PricingCalculator: ...
  ```

#### ARCH-055 — Every Python package directory has an __init__.py
- **Level:** SHOULD · **Automation:** full · **Tier:** full · **Category:** structure
- **Validation:** `ast-checker` — filesystem check - every directory under src/ holding a .py file has __init__.py
- **Description:** Every directory under src/ that contains a .py file (directly or in a subdirectory) has an __init__.py, including empty ones. Implicit namespace packages (PEP 420) are not used.
- **Rationale:** An explicit __init__.py marks a directory as a package on purpose, rather than by the accident of holding a .py file; it also avoids the edge cases implicit namespace packages create for some tooling and IDEs. A missing one is easy to overlook when scaffolding a module by hand.
- **Correct:**
  ```
  sales/orders/domain/model/__init__.py   # empty, present
  sales/orders/domain/model/aggregate.py
  ```
- **Incorrect:**
  ```
  sales/orders/domain/model/aggregate.py  # no __init__.py alongside it
  ```

---

# 10. DDD Rules

## 10.1 Decision tree - adding behavior

```text
Adding behavior?
├── Does it protect an invariant of ONE aggregate?        → method on the aggregate
├── Does it span MULTIPLE aggregates?                      → domain service
├── Is it choosing between MULTIPLE runtime strategies?    → policy
├── Is it a reusable predicate used in 2+ places?          → specification
├── Is it multi-step coordination + persistence + events?  → application service method
└── Is it translating a stimulus or a response?            → entrypoint / mapper
```

## 10.2 Tactical pattern selection - when yes, when no

### Value Object

- **Use when:** the concept is described by its values (`Money`, `Email`, `DateRange`,
  `Quantity`), has no lifecycle, and needs centralized validation and value equality.
- **Do not use when:** it needs identity over time (use an Entity), or it is a bare
  primitive with no invariants (avoid wrapper obsession).
- **Shape:** `@dataclass(frozen=True)`, validate in `__post_init__`, no setters,
  methods return new instances. (ARCH-031)

### Entity

- **Use when:** the concept has a stable identifying ID even as attributes change, and
  its history matters.
- **Do not use when:** it is interchangeable by value (use a Value Object), or it
  exists only inside another entity and is never referenced from outside.
- **Shape:** identity by ID, mutation only via business-named methods, no setters that
  enable invalid state. (ARCH-018)

### Aggregate and Aggregate Root

- **Use when:** invariants span several objects and must always hold.
- **Do not use when:** the objects are unrelated - do not lump them together.
- **Shape:** access and mutate only via the root (ARCH-019); reference other
  aggregates by ID (ARCH-020); one transaction modifies one aggregate (ARCH-021, MUST
  with documented justification); validate invariants on every mutation. The God
  Aggregate smell: more than roughly 7 invariants, or hundreds of loaded children.

### Domain Service

- **Use when:** logic involves multiple aggregates and belongs to none, or needs a
  domain port.
- **Do not use when:** the logic fits on an aggregate (anemic domain), it is
  orchestration (use an application service), or it is a pure calculation over one
  aggregate (use an aggregate method).
- **Shape:** stateless, takes aggregates and value objects as parameters, I/O only via
  `domain/model/ports.py`, knows nothing about transactions or DTOs.

### Domain Event

- **Use when:** another part of the same context reacts to a state change in a
  decoupled way, or the fact must be recorded to derive integration events.
- **Do not use when:** the reaction is part of the same invariant and transaction, or
  it is cross-context communication (use an integration event).
- **Shape:** `frozen`, past tense, no side-effects, carries `occurred_at` plus the
  needed IDs, dispatched after persistence. (ARCH-023)

### Repository (abstraction)

- **Use when:** an aggregate root needs persistence and retrieval by identity or
  specification.
- **Do not use when:** the query is a complex multi-aggregate read (use a read model),
  or you would add `find_x_with_y() -> DTO` (Repository as business service).
- **Shape:** interface in `domain/model/ports.py`, methods at root level (`get`, `add`,
  `save`, `next_identity`), returns aggregates, not rows or DTOs. (ARCH-022)

### Factory

- **Use when:** building a valid aggregate needs non-trivial logic, or reconstruction
  from persistence differs from fresh creation.
- **Do not use when:** it would only wrap the constructor.
- **Shape:** prefer a `@classmethod` on the aggregate (`Order.place(...)`) unless the
  logic is large or needs a port.

### Specification

- **Use when:** the same selection or validation rule is used in 2+ places, or rules
  combine dynamically.
- **Do not use when:** it is a one-off rule (`order.is_cancellable()`), or purely to
  filter in the database.
- **Shape:** stateless, `is_satisfied_by(candidate) -> bool`.

### Policy

- **Use when:** there are multiple real strategies for a decision chosen at runtime.
- **Do not use when:** there is a single rule, or "policy" actually means
  authorization or rate-limiting (that is an application or adapter concern).
- **Shape:** interface plus implementations in `domain/`.

---

# 11. Testing Strategy

## 11.1 Pyramid

| Level | Tests | Dependencies | Speed |
|---|---|---|---|
| Domain | aggregates, VOs, services, specs, policies - invariants and rules | none, real objects | us |
| Application | service methods (use cases) - orchestration, transaction, events published | real domain + in-memory fakes of the ports | ms |
| Adapter / integration | each adapter against its real technology | real DB/broker (testcontainers) | s |
| Contract | integration event schema, producer to consumers | schema fixtures | ms |
| End-to-end | full flow through a real entrypoint | context stack | s+ |

## 11.2 Naming

`given_<state>__when_<action>__then_<result>` - a double underscore separates the three
parts. Example:
`given_shipped_order__when_add_item__then_raises_order_already_shipped`. (ARCH-040)

## 11.3 Mock / do not mock

- **Never mock:** domain objects (aggregates, VOs, services), the code under test,
  `shared_kernel` VOs. (ARCH-038)
- **Use in-memory fakes, not mocks:** repositories (`InMemoryOrderRepository` over a
  dict, bound to an `InMemoryUnitOfWork`), `EventBus` (`RecordingEventBus`), `Clock`
  (`FixedClock`). The same contract test runs against the fake and the real adapter -
  the fake cannot lie. (ARCH-039)
- **Mock only in adapter tests:** the third party's SDK when testing your adapter - and
  even then prefer a fake server, VCR, or testcontainer.
- **Rule of thumb:** an application test with more than 1 to 2 mocks means the service
  does too much or dependencies are not properly injected.

## 11.4 Per-layer guidance

- **Aggregates:** pure objects, never through the repository. Assert new state, emitted
  domain events, and that invalid cases raise the correct domain exception. One test
  per rule, not per method. Domain tests run without the store's mapping or translation
  configuration - an autouse fixture ensures aggregate classes stay uninstrumented
  (with the SQLAlchemy reference impl, `configure_mappings()` is not called).
- **Application services:** real domain + fakes. Assert the right aggregate was loaded,
  the business method was called, persistence happened, the expected integration events
  were published, and the transaction commits or rolls back. Do not re-test domain
  rules here. Test rollback explicitly.
- **Adapters:** repository round-trip (`add` -> `get` -> full equality) plus
  specification-to-query translation; publisher and consumer against a real broker,
  with the serialized message matching the Published Language schema.
- **Contract tests:** producer - every emitted event validates against its published
  schema; consumer - inbound fixtures validate against the producer schema
  (consumer-driven: removing a field the consumer uses breaks the build). A schema
  change means a new event version, never an in-place edit.

## 11.5 Coverage as a rule

Domain above 90% (pure, cheap). Application: every use case with happy path, rollback,
and events. Adapters: round-trip plus error translation. E2E: critical business flows
only.

---

# 12. Anti-patterns

| Anti-pattern | Why it is a problem | Alternative |
|---|---|---|
| Anemic Domain Model | logic scattered in services, invariants unprotected | behavior on the aggregate |
| God Aggregate | huge transactions, lock contention, not extractable | split by real consistency boundaries; reference by ID |
| God / Fat Application Service | a service class that grows unbounded: many methods, many unrelated concerns, many deps | one service per aggregate module (Section 6.2); the checker warns past ~7 methods, ~200 lines, or 5 constructor params - look at the aggregate before splitting the service |
| Fat Controller / Fat Entrypoint | untestable without transport, logic not reusable | entrypoint only translates + calls one service method |
| Business logic in adapters | hidden from domain tests, duplicated | adapters only translate; decisions in domain/application |
| Repository as business service | business queries leak into persistence, repo grows unbounded | repo = collection of roots; complex reads -> read model |
| Domain imports adapters / frameworks | domain not testable in isolation, tech locked in | DIP - domain defines ports, adapters implement |
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

# 13. MUST / SHOULD / MAY

| Level | Meaning | On deviation |
|---|---|---|
| MUST | architectural invariant | build fails, no merge. Exception = documented ADR + standard maintainer approval |
| SHOULD | strong default | allowed with a one-line justification in the PR or an ADR; reviewer must acknowledge |
| MAY | genuine project choice | documented so it reads as sanctioned, not accidental |

`MUST*` is a conditional MUST: it applies when the stated condition holds (for example
ARCH-021 and ARCH-036).

## Exception process

A `docs/adr/NNNN-*.md` file records the rule waived, the reason, the scope, and a
mandatory `expires:` date (default 90 days). The validator generates its allowlist from
non-expired ADRs only - a lapsed waiver silently re-activates the rule and fails the
next build, forcing a conscious renew-or-fix. CI prints the count of active waivers per
rule on every PR.

---

# 14. Architecture as Code

## 14.1 Tooling map (Python)

| Mechanism | Tool | Rules | Runs in |
|---|---|---|---|
| Import contracts (layering, independence, cycles) | import-linter (`.importlinter`) | 001-003, 005, 006, 008, 011-015, 017, 034, 035 | CI + pre-commit |
| Import-graph queries / bespoke asserts | grimp | 007, cycle detection, "who imports X" | pytest arch suite |
| Banned symbols/patterns per layer | ruff (`flake8-tidy-imports` banned-api, `TID`, `TCH`) | 003, 004, 028 | CI + pre-commit |
| AST structural rules | custom `ast` checker shipped with the standard | 023, 031, 018, 019, 030 (service size: methods/lines/params), 040, 041 (promotion thresholds), 043 (envelope shape) | CI + pytest |
| ADR waiver expiry | validator date check over `docs/adr/` | 021*, 036, any waived MUST | CI |
| Package boundaries with a public API | tach (`tach.toml`) | 012, 042, 045 | CI |
| Event schema / contract testing | pydantic/jsonschema export + consumer fixtures; optionally Pact | 024, 043, 044 | CI (producer & consumer) |
| Test taxonomy | pytest markers + a conftest rule forbidding adapter imports in domain tests | 038 | CI |
| Coverage gates per layer | coverage.py with per-path thresholds | Section 11.5 | CI |
| Manual review checklist | shipped PR checklist for the "manual" rules | 016, 021*, 027, 029, 036, 039, 042 | code review |

## 14.2 Confidence tiers

- **full** (~20 rules): deterministic pass/fail on the exact rule.
- **partial** (~14 rules): catches common violations; edge cases need review.
- **manual** (~6 rules): only a human or an LLM reviewer can judge.

## 14.3 The validator

A single entrypoint `python -m arch_standard.check` runs import-linter plus the AST
checker plus schema validation and prints:

```text
ARCH-001  PASS
ARCH-012  FAIL  sales/application/order_placement.py:4  imports billing.domain.invoice
ARCH-023  FAIL  sales/domain/model/events.py:12         OrderCreate is not past-tense / not frozen
```

It exits non-zero on any MUST failure and warns on SHOULD.

---

# 15. Structure Thresholds

The folder shape is fixed (Section 2.1), so there is no promotion step and no "when do
I restructure?" judgement. What remains are a few size signals that mean a model
problem, not a layout problem:

| Signal | Threshold (starting point, tune per project) | What it actually means |
|---|---|---|
| `<module>/application/<aggregate>.py` | > ~7 public methods, > ~200 lines, or > 5 constructor params (checker warns) | The aggregate is probably doing too much. Look at the aggregate boundary before splitting the service. |
| `<module>/domain/model/aggregate.py` | > ~400 lines or > ~7 invariants | God Aggregate. Split into two aggregate modules. |
| `<module>/domain/model/ports.py` | > ~8 protocols in one aggregate module | The aggregate depends on too much of the outside world. |
| `<context>/shared/` | anything beyond IDs, policy-free VOs, and cross-aggregate domain services | ARCH-047 violation, or the aggregates are wrongly separated. |
| Cross-aggregate atomicity needed | more than occasionally | The aggregate boundaries are drawn wrong (Section 3.6). Redraw before adding any coordinating construct. |
| Reads through the aggregate | complex joins, reporting, dashboard shapes | Introduce a dedicated read model in `<context>/read/` (Section 2.5). |
| Cross-context integration | more than one team, or independent deployability needed | Move from an in-process gateway to async events + ACL as the default. |
| Outbound adapters of one kind | many (e.g. 5+ external clients) in one module | Sub-folder within that module's `adapters/`. |

Most of these signals point at the model, not at the folders. That is the intended
effect of fixing the shape: when something hurts, the structure is no longer a
candidate explanation. (ARCH-041)

---

# 16. Reuse

The canonical repository is laid out as a pipeline: a machine-readable rule catalog is
the source of truth, and every other artifact is generated from or driven by it.

```text
architecture-standard/   (canonical)
├── ARCHITECTURE_STANDARD.md          # human spec (English), generated from rules/ + prose
├── rules/*.yaml                      # machine-readable catalog - source of truth
├── checks/                           # the validator: import-linter template + AST checker + schema tools
├── templates/                        # project skeleton (copier)
├── skills/architecture/SKILL.md      # the Superpowers skill
└── reviewers/architecture-reviewer/  # subagent definition
```

## Consumption paths

1. **Human** - reads `ARCHITECTURE_STANDARD.md`.
2. **New project** - `copier copy` produces the `src/` skeleton plus `.importlinter`,
   CI, and the `check` command.
3. **Superpowers skill** - triggers on "new bounded context", "add a use case", "where
   does X go", "review architecture". Loads the relevant rule subset plus the decision
   trees. Points Claude Code at `rules/*.yaml`.
4. **architecture-reviewer subagent** - given a diff, loads `rules/`, runs `checks/`,
   judges the "manual" rules with an LLM, and posts an `ARCH-xxx PASS/FAIL` report as
   PR comments.
5. **CI** - runs `checks/` on every PR; MUST failures block.

## Authoring constraints for agent-consumability

- Every rule has a stable ID, a single level, an `automation` field, a one-paragraph
  rationale, and one correct plus one incorrect example.
- The rule catalog is YAML (source of truth); Markdown is generated.
- Decision guidance is given as decision trees and checklists, not prose.
- Structure is given as a literal tree plus a "what goes where" table.
- Every rule is self-contained - no "as discussed above".
