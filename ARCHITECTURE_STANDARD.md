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
- **Ports.** `abc.ABC` with `@abstractmethod` (nominal typing; adapters inherit
  explicitly, so a missing method fails at instantiation, not at first call). Three
  homes: `commons/types/` (generic technical ports), the aggregate module's
  `domain/model/ports.py` (domain vocabulary), and colocated in the use-case module
  (non-domain outbound). There is no `application/ports.py` by default. The one
  exception is `commons.types.events.DomainEvent`, still a `Protocol`: concrete domain
  events are independent per-module dataclasses that must never inherit from a
  commons type (see its docstring).
- **Persistence.** The normative contract (the `UnitOfWork` ABC, repository ports,
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
  `application/`. `src/commons/` is the only code area above an aggregate, and it is
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
│   │   ├── entrypoints/             # inbound adapters, context-wide, grouped by kind
│   │   │   ├── web/                 #   HTTP/GraphQL - one file per aggregate module
│   │   │   │   └── <aggregate>.py
│   │   │   ├── events/              #   message/event consumers - one file per concern,
│   │   │   │   └── <concern>.py     #     named for what it does (Section 4.2)
│   │   │   ├── crons/               #   scheduled jobs - same naming as events/
│   │   │   │   └── <concern>.py
│   │   │   └── cli.py               #   CLI (flat; split into cli/ the same way if needed)
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
│   │   │   │   ├── <aggregate>.py         # one method per use case
│   │   │   │   └── <aggregate>_finder.py  # THIS aggregate's own listing/search/filter/
│   │   │   │                              #   sort/pagination query, when it needs one
│   │   │   │                              #   (Section 2.5): a Finder ABC + its query/
│   │   │   │                              #   result DTOs, entrypoint-importable like
│   │   │   │                              #   any other application module - not
│   │   │   │                              #   read/, which is for queries spanning 2+
│   │   │   │                              #   aggregate modules
│   │   │   └── adapters/
│   │   │       ├── <aggregate>_repository.py
│   │   │       ├── <aggregate>_finder.py  # the Finder ABC's implementation, wired by
│   │   │       │                          #   bootstrap/ like the repository - never
│   │   │       │                          #   imported by entrypoints directly (ARCH-009)
│   │   │       ├── mapping.py             # aggregate to stored-form translation
│   │   │       └── <adapter>.py           # one module per outbound adapter
│   │   ├── <aggregate_module_2>/    # same shape, one per aggregate
│   │   └── read/                     # Read/Query layer - projections, reporting,
│   │                                 #   dashboards, and any read spanning 2+ aggregate
│   │                                 #   modules. Returns DTOs. Imports no aggregate
│   │                                 #   module's domain/ or application/. May query
│   │                                 #   the store directly.
│   ├── commons/                      # THIS PROJECT's own portion of the `commons`
│   │   │                             #   namespace package - everything above one
│   │   │                             #   aggregate. No __init__.py (ARCH-055).
│   │   ├── ids.py                    #   ID types referenced across aggregates
│   │   ├── geo.py                    #   transversal VOs / enums / catalogues
│   │   ├── services.py               #   domain services spanning aggregates (rare)
│   │   └── adapters/                 #   framework-bound technical adapters shared
│   │       │                         #   across contexts, not (yet) proposed
│   │       │                         #   upstream into arch-commons (Section 8.3).
│   │       │                         #   No __init__.py either (ARCH-055) - merges
│   │       │                         #   with arch-commons' own commons/adapters/.
│   │       └── <adapter>.py
│   └── bootstrap/                    # Composition Root: config, singletons, DI container,
│                                     #   service/UoW factories, router registration,
│                                     #   consumer startup - constructs adapters
│                                     #   defined elsewhere, does not define them
│                                     #   (ARCH-059)
└── tests/                            # mirrors src/'s shape 1:1 (Section 11.3):
    └── <context>/<aggregate_module>/<layer>/test_<unit>.py
```

`adapters/` holds a module's **outbound (driven) adapters**: repositories, gateways,
clients. `entrypoints/` holds the context's **inbound (driving) adapters**: HTTP, consumers,
CLI. Both are adapters; the folder names say which side of the core they sit on.

`commons` is a **PEP 420 namespace package with two portions**. `commons.types` and
`commons.adapters` ship from `arch-commons`, an installed, separately versioned package
that every project depends on, so a fix reaches all of them at once (Section 8.1).
`src/commons/` is this project's own portion: it merges with the installed one at import
time, so `commons.types.errors` and `commons.geo` both resolve while living in different
distributions. Neither side carries a top-level `__init__.py` - a regular package on
either side would shadow the other outright instead of merging (ARCH-055).

`src/commons/` is the single home for anything above one aggregate. Unlike
`commons.types`, it MAY carry business meaning - that is what it is for. What it may
not do is import a context (ARCH-014): the dependency is one-way, and a concept a
commons module needs is promoted into commons rather than imported down from a context.

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
and those ID types live in `commons/ids.py`. (ARCH-046)

## 2.3 What goes where

| You are adding... | It goes in... |
|---|---|
| A new business boundary | `src/<context>/` |
| A new aggregate | `src/<context>/<aggregate_module>/` (a new folder, full shape) |
| A rule that protects an invariant of one aggregate | a method on the aggregate in `<module>/domain/model/aggregate.py` |
| A calculation over one aggregate that is not a method | `<module>/domain/services/` (one file per domain service; named after the aggregate if there's only one, e.g. `quote.py`) |
| A calculation spanning aggregates | `commons/services.py` |
| A use case (state change on one aggregate) | a method on `<module>/application/<aggregate>.py` |
| A persistence/broker/third-party integration | one module in `<module>/adapters/` |
| A contract the domain needs | `<module>/domain/model/ports.py` |
| A non-domain outbound contract used by one use case | an `abc.ABC` colocated in that `application/` module |
| A fact other parts of this context react to | a domain event in `<module>/domain/model/events.py` |
| An ID type referenced by another aggregate | `commons/ids.py` |
| A value object, enum or reference catalogue used above one aggregate | `src/commons/<concept>.py` |
| A listing/search/filter/sort/pagination query over ONE aggregate module's own data | a Finder ABC + DTOs in `<module>/application/<aggregate>_finder.py`, implemented in `<module>/adapters/<aggregate>_finder.py` - not `<context>/read/` |
| A projection, report, dashboard, or any read spanning 2+ aggregate modules | `<context>/read/` |
| A dependency-free technical primitive | the `arch-commons` package, `commons.types` (propose upstream) |
| A shared framework-bound technical implementation | propose upstream into the `arch-commons` package, `commons.adapters`; until accepted, or if project-specific, `src/commons/adapters/` (Section 8.3) |
| A domain concept shared by 2+ contexts, with business policy | `src/commons/<concept>.py` |
| Wiring / config / DI | `bootstrap/` |

## 2.4 There is no context-level `application/`

DDD has no "application service of the context" - application services are per use
case and belong with the model they coordinate. Cross-aggregate flow is handled by the
rules in Section 3.6, not by a coordinating layer.

There is no context-level code area at all. Anything above one aggregate - whether it
crosses two aggregates of one context or two contexts - goes to `src/commons/`, which
is strictly limited to the things in the table above: ID types, value objects, enums
and reference catalogues, domain services spanning aggregates, and - held to
adapters/-layer discipline instead, in `commons/adapters/` - framework-bound technical
adapters shared across contexts (Section 8.3). It never holds an aggregate root, a
repository, or an application service. (ARCH-047)

One boundary is deliberately traded away here. A context-scoped shared area would
confine sharing to one context; `commons/` is visible to all of them, so two contexts
can come to depend on the same concept. The one-way import rule is what keeps that
honest: `commons/` never imports a context, so the coupling can only ever be a
deliberate promotion into `commons/`, never a quiet reach sideways.

## 2.5 The Read/Query layer

Repositories are responsible for persistence and retrieval of aggregate roots. They
must not be used as general-purpose query interfaces.

Three cases, three homes - the second one is easy to get wrong, so it gets its own
row:

| The query needs... | It goes in... |
|---|---|
| One aggregate, by id | that aggregate module's own repository (`get`) |
| One aggregate, by anything else - search, filter, sort, a paginated listing | a Finder in that aggregate module (below) |
| 2+ aggregate modules, or a projection/report/dashboard that reshapes data no single aggregate owns | `<context>/read/` |

**A listing is not automatically a Read/Query-layer concern just because it returns
more than one row or is not a plain get-by-id.** `<context>/read/` exists at context
level, not inside an aggregate module, for one reason: the reads that need it are the
ones that span aggregate modules. A query that reads only one aggregate module's own
data - however many rows it returns, however it is filtered, sorted or paginated - has
nothing to span. Promoting it to context level buys nothing and costs a real thing: a
second copy of that aggregate's row shape living in a file nobody outside the module
needed to share.

**A Finder is a port, exactly like a repository - not a class an entrypoint reaches
into `adapters/` for.** ARCH-009 forbids entrypoints from importing a module's
`adapters/` directly for the same reason it forbids constructing an adapter inline:
an entrypoint gets its collaborators wired by the composition root, never imported
from the layer that touches the store. A repository resolves this by splitting in
two - the `Repository` ABC in `domain/model/ports.py` (importable), its
`InMemoryXRepository` implementation in `adapters/` (never imported by an
entrypoint, only constructed by `bootstrap/`). A Finder splits the same way, in the
layer the three-homes rule (ARCH-042) already gives it: it deals in DTOs, not
aggregates, so it is not domain vocabulary - it is "a non-domain outbound contract
used by one use case," which the three-homes rule already sends to the use-case
module. So:

- The `Finder` ABC, and its query/result DTOs (`ListX`, `XListItem`), live in
  `<module>/application/<aggregate>_finder.py` - an application module like any
  other, freely importable by entrypoints.
- `InMemoryXFinder(Finder)` - the implementation - lives in `<module>/adapters/`,
  next to the repository whose rows it reads. `bootstrap/` constructs it and hands
  the `Finder`-typed instance to the entrypoint's `configure()`, exactly like the
  service.
- The Finder MAY query the store directly, bypassing the aggregate and the Unit of
  Work: a read model is not bound by write-side invariants. Its implementation stays
  out of `domain/` for the same reason a repository's does.
- Entrypoints call the Finder directly for a query; they do not route it through the
  application service, which would add nothing (the service exists to enforce
  invariants on writes, and a query does not write).

`<context>/read/` is the same shape scaled up one level, for the cases that
genuinely span aggregate modules:

- `read/` MAY query the store directly, for the same reason a Finder may.
- `read/` MUST NOT import any aggregate module's `domain/` or `application/`.
  (ARCH-052)
- `read/` returns DTOs, never aggregates.
- Entrypoints call `read/` directly for queries, for the same reason they call a
  Finder directly.

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

## 4.2 Structure: grouped by transport kind, one file per aggregate

`<context>/entrypoints/` groups by transport kind, not by a single flat file per
kind:

```text
<context>/entrypoints/
├── web/            # HTTP/GraphQL routes and other request/response APIs
│   ├── order.py    #   one file per aggregate module
│   └── customer.py
├── events/         # message/event consumers (Kafka/RabbitMQ/SQS/...)
│   └── order_placed.py    #   named for what it does; not forced into an
│                           #   aggregate-name pattern the way web/ is
├── crons/          # scheduled jobs
│   └── expire_stale_orders.py
└── cli.py          # CLI stays a flat file; add a cli/ folder the same way
                     #   if it ever needs to split
```

There is no `providers.py`. Each entrypoint file defines its own tiny
getter for the one service it needs (a `configure()`/`get_x_service()` pair,
or the transport's own DI hook), set once at startup by the composition root
(`main.py`) -- the only module allowed to import `bootstrap/` (ARCH-017).
This keeps each aggregate module's wiring self-contained: extracting
`quote/` into its own service later needs no untangling of a
context-wide wiring file shared with other aggregate modules.

`web/` gets one file per aggregate module because a REST-style resource maps
cleanly onto one aggregate. `events/` and `crons/` do not: an event consumer or a
scheduled job is better named for the specific thing it does
(`order_placed.py`, `expire_stale_orders.py`) than forced into
`<aggregate_name>.py`. What both share is the real rule underneath the naming:
**a file serves at most one aggregate module** - split it, don't let one handler
reach into two aggregates' application services (ARCH-056). `entrypoints/`
groups by transport kind first because everything under one kind shares
concerns (a router, a consumer group, a scheduler) that a per-aggregate split
alone does not.

## 4.3 Rules

- Entrypoints are inbound adapters: HTTP, GraphQL, Kafka/RabbitMQ/SQS consumers, CLI,
  cron.
- An entrypoint translates a stimulus into a command/query, calls one application
  service method, and maps the result or exception back to the transport (status codes,
  serialization). (ARCH-004 family)
- An entrypoint obtains a fully wired service through its own getter, configured once
  at startup by `main.py` (the composition root). It MUST NOT construct outbound
  adapters itself, and MUST NOT import `bootstrap/` itself. (ARCH-009, ARCH-017)
- An entrypoint MUST NOT call persistence, adapters, or the database directly
  (`repo.save(...)`, `session.execute(...)`, `http_client.get(...)`). The only thing it
  calls is the application service. (ARCH-009)
- An entrypoint MUST NOT contain business logic. (ARCH-010, SHOULD)
- An entrypoint MUST NOT call another entrypoint. (ARCH-011)
- An entrypoint file serves at most one aggregate module. (ARCH-056, SHOULD)
- An entrypoint MAY import `domain/model/exceptions.py` (and the `commons` base errors)
  solely to map domain exceptions to transport responses.
- Pydantic request/response models live only in entrypoints.

## 4.4 Exceptions to the rule

- Health and readiness endpoints MAY read backing-service state directly; they are not
  business use cases.
- A pure pass-through admin or debug endpoint MAY be exempt if it is explicitly marked
  and excluded from the public surface. This is discouraged and requires justification.

## 4.5 HTTP response shaping is centralized, not per-handler

When a web entrypoint context wants a uniform response shape -- a success/error
envelope, standard error formatting, a consistent status-code mapping -- that shaping
is applied by **one mechanism the composition root registers once** (e.g. ASGI
middleware added in `main.py`), never rebuilt inside each handler. (ARCH-057, SHOULD)

```text
bootstrap/envelope.py    # e.g. an ASGI middleware wrapping every JSON response
main.py                  # app.add_middleware(EnvelopeMiddleware) -- registered once
<context>/entrypoints/web/order.py   # handlers return their plain response model;
                                      #   they never build the envelope themselves
```

The envelope's exact shape (field names, whether errors are a list or a single
message, which status codes map where) is a project decision this rule does not
mandate. What it does mandate is *where* that decision lives: one place, applied
uniformly, not duplicated -- and inevitably drifting -- across every handler.

---

# 5. Domain

## 5.1 Contents and dependencies

`domain/` contains: `model/` (aggregates, entities, value objects, domain events,
ports, projections, exceptions), `services/` (one file per domain service; named
after the aggregate when there's only one, e.g. `quote.py`), and `specifications.py`.

`domain/` depends on: the standard library, `commons/types/`, and (rarely)
`src/commons/`. Nothing else. No frameworks, no I/O, no ORM, no `datetime.now()` or
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

class OrderNotifier(ABC):                # colocated non-domain outbound contract
    @abstractmethod
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
  `PaymentGateway`, cross-context gateways): the explicit `abc.ABC` is optional
  (SHOULD) - write it when the seam benefits from being explicit (testing,
  type-checking, multiple implementations, agent-readability), and skip it
  (duck-typed injection) for a trivial single-implementation dependency. Injection is
  never optional: the concrete adapter is built by the composition root
  (`bootstrap/`, `main.py`) and injected; `application/` never imports it.

Three homes, one rule each:

| Home | What lives here | The test |
|---|---|---|
| `commons/types/` | generic technical ports (`abc.ABC`): `Clock`, `UnitOfWork`, `EventBus`, `IdGenerator` | dependency-free, no business meaning, reusable in any project |
| `domain/model/ports.py` | domain-vocabulary contracts: repositories, domain-service providers (`PricingPolicyProvider`) | you would mention it describing the business; a domain object or the repository abstraction needs it |
| an `abc.ABC` colocated in the use-case module | non-domain outbound contracts the orchestration needs: `EmailSender`, `PaymentGateway`, cross-context gateways (`CreditCheckPort`) | only `application/` uses it; it is integration plumbing, not domain language |

- No `application/ports.py` file by default - colocated `abc.ABC` classes are the
  mechanism. (ARCH-042, SHOULD)
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

`commons/types/unit_of_work.py` holds the `UnitOfWork` ABC. It owns the
transaction and domain-event collection. It says nothing about a specific database.

```python
class UnitOfWork(ABC):
    @abstractmethod
    def __enter__(self) -> "UnitOfWork": ...
    @abstractmethod
    def __exit__(self, *exc: object) -> None: ...      # rollback if commit() was not called
    @abstractmethod
    def commit(self) -> None: ...
    @abstractmethod
    def rollback(self) -> None: ...
    @abstractmethod
    def track(self, aggregate: object) -> None: ...    # repositories call this on load/store
    @abstractmethod
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
class SqlAlchemyOrderRepository(OrderRepository):  # explicit inheritance, not duck-typed
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
# bootstrap/__init__.py
def build_container() -> Container:
    uow = SqlAlchemyUnitOfWork()                  # mappings already configured
    orders = SqlAlchemyOrderRepository(uow)
    service = OrderService(uow=uow, orders=orders, bus=EventBus(), notifier=Notifier())
    return Container(order_service=service)
```

### Other stores

The same `UnitOfWork` ABC, the same repository ports, and the same `track()` /
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
aggregate classes stay uninstrumented (guarded by a fixture). See Section 11.5. Every
use-case write goes through a UoW; the service never commits repositories
individually. (ARCH-033)

## 7.3 Transactional outbox

- Mandatory when event publication or a transactional side-effect requires a delivery
  or consistency guarantee: integration events are written to an `outbox` table in the
  same transaction; a separate process publishes them. (ARCH-036)
- Optional (`publish-after-commit`) when no such guarantee is required.
- The machinery lives in `commons/adapters/outbox.py`.

---

# 8. commons/

`commons` is a single **PEP 420 namespace package assembled from two portions**, and
everything above one aggregate lives in it. There is no `shared_kernel/` and no
`<context>/shared/`: one home, one set of admission rules, one import direction.

| | `commons.types` / `commons.adapters` | `commons.<module>` |
|---|---|---|
| Ships from | the installed `arch-commons` package | this project's own `src/commons/` |
| Content | dependency-free technical primitives, ports, and framework-bound shared implementations | this project's transversal domain concepts |
| Business meaning | **forbidden** (ARCH-016) | **expected** - that is what it is for |
| Governed by | semver on `arch-commons` | this project's own review |

Neither portion carries a top-level `commons/__init__.py`. A regular package on either
side would shadow the other outright rather than merge with it, so both are namespace
portions and `src/commons/` is the one directory under `src/` that MUST NOT have an
`__init__.py` (ARCH-055). `commons/adapters/` — the project's own carve-out described in
8.3 — repeats the same merge one level down, and is the second and only other such
directory (ARCH-055).

## 8.1 `arch-commons` - a separately versioned package

`commons.types` and `commons.adapters` are not vendored into each project. They are
published as `arch-commons` and declared as a dependency, so a fix or a new primitive
reaches every project that upgrades instead of drifting into N divergent copies. This
is what makes the standard usable as the base of many repositories rather than a
one-off scaffold.

| | `commons.types` | `commons.adapters` |
|---|---|---|
| Content | dependency-free technical primitives and ports (`abc.ABC`, `@abstractmethod`) | framework-bound shared implementations |
| Examples | `DomainError`/`ApplicationError` bases, `EntityId`, `Pagination`, `Clock` / `EventBus` / `IdGenerator` / `UnitOfWork` ABCs (`DomainEvent` stays a `Protocol` - see its docstring) | `SqlAlchemyUnitOfWork`, `InMemoryUnitOfWork`, outbox machinery, each explicitly inheriting its `commons.types` ABC |
| Importable by | everyone, including `domain/` | only `adapters/`, `entrypoints/`, `bootstrap/`, tests |
| Forbidden | any business meaning, any framework import | - |

**Governance.** `arch-commons` follows semver, with the same compatibility policy as
the standard itself: a breaking change to `commons.types` is a major bump and is
announced with migration notes. Adding a primitive is a minor. Consuming projects pin
a version and upgrade deliberately.

**Contributing upward.** A technical primitive that a project invents locally, and
that a second project would want, does not get copied - it is proposed upstream into
`arch-commons`. A framework-bound one lives, until accepted (or if it never is - some
adapters are tuned to one project's concurrency model and are not generic enough to
upstream), in that project's own `commons/adapters/` (8.3), clearly marked.

Rules: ARCH-015 (`commons.types` imports nothing from contexts, application, adapters,
or the project's own commons modules), ARCH-016 (`commons.types` has no business
logic), ARCH-034 (`commons.adapters` not imported by domain/application), ARCH-035
(`commons.types` imports no framework).

## 8.2 The project's own `commons/` modules

`src/commons/` holds the concepts this project needs above a single aggregate: ID types
referenced across aggregates, value objects, enumerations and reference catalogues, and
the rare domain service spanning aggregates. One file per concept, named for the
concept - `commons/geo.py`, `commons/ids.py`, `commons/money.py`.

Unlike `commons.types`, these MAY encode business policy. A list of the municipalities a
business operates in, a tax rule, an accounting rounding convention - all belong here if
more than one aggregate needs them. The test is no longer "does it encode a policy?" but
simply "is it needed above one aggregate?".

What it may never do is depend downward:

| Direction | Allowed? |
|---|---|
| any context → `commons` | yes, freely |
| `commons` → any context | **no** (ARCH-014) |
| `commons.<module>` → `commons.types` | yes |
| `commons.types` → `commons.<module>` | **no** (ARCH-015) - `arch-commons` ships independently and cannot see them |

When a commons module needs a concept that currently lives in a context, the concept is
**promoted into commons**, not imported down from the context. That promotion is the
only way a concept becomes shared, which is what keeps the sharing deliberate and
visible instead of accumulating by accident.

`commons/` never holds an aggregate root, a repository, or an application service
(ARCH-047). Business meaning is not licence to put behaviour-owning objects there.

Generic subdomains (notifications, identity) are other bounded contexts, not shared
code - consumed via the Section 3 mechanisms.

## 8.3 The project's own `commons/adapters/`

A framework-bound technical adapter used by more than one context - a UnitOfWork
variant, a shared cache client, anything that would belong in `arch-commons`'
`commons.adapters` but is not (yet) proposed upstream, or is specific enough to this
project that upstreaming never applies - lives in `src/commons/adapters/`, this
project's own mirror of `arch-commons`' `commons.adapters` portion. It merges with
that portion at import time exactly the way `commons/` merges with `commons.types` and
`commons.adapters` as a whole: neither side carries a `commons/adapters/__init__.py`
(a regular package on either side would shadow the other), so `commons/adapters/` is
the second directory under `src/` that MUST NOT have one (ARCH-055) - every directory
nested inside it does, as normal.

`commons/adapters/` follows **adapters/-layer discipline throughout**, not the domain
discipline the rest of `commons/` is held to:

| | rest of `commons/` (`ids.py`, `geo.py`, `services.py`, ...) | `commons/adapters/` |
|---|---|---|
| Framework imports | forbidden (ARCH-003) | allowed |
| `*Service`/`*Repository` names | banned (ARCH-047) | normal |
| Mutable state | forbidden outside `services.py`'s own narrow carve-out | expected |
| Business meaning | expected | **forbidden** - same as `commons.adapters` upstream |

It holds one thing only: a technical adapter implementation, typically subclassing a
`commons.types` ABC exactly like its upstream counterparts do. It never holds a port
(a port lives in `commons/types/`, upstream, per the three-homes rule, ARCH-042), an
aggregate, or business logic of any kind (ARCH-047).

`bootstrap/` constructs instances of adapters defined here (or anywhere else) and
wires them into services; it does not define adapter classes itself (ARCH-059) - a
class implementing a port belongs in an adapters/ directory, not the composition
root, whether or not it happens to work either way.

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
| ARCH-009 | Entrypoints obtain wired services from the composition root; never construct or call outbound adapters directly | MUST | partial |
| ARCH-010 | Entrypoints contain no business logic | SHOULD | partial |
| ARCH-011 | Entrypoints call application services, not other entrypoints | MUST | full |
| ARCH-012 | A context imports nothing from another context | MUST | full |
| ARCH-013 | No dependency cycles between contexts | SHOULD | full |
| ARCH-014 | commons imports nothing from any context | MUST | full |
| ARCH-015 | commons/types imports nothing from contexts, application, adapters, or project commons modules | MUST | full |
| ARCH-016 | commons/types contains no business logic | MUST | manual |
| ARCH-017 | Nothing imports bootstrap | MUST | full |
| ARCH-034 | commons/adapters is not imported by domain or application | MUST | full |
| ARCH-035 | commons/types does not import any framework | MUST | full |
| ARCH-057 | HTTP entrypoints centralize response shaping in the composition root | SHOULD | manual |

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
| ARCH-058 | A test file's directory mirrors the source it tests | SHOULD | partial |

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
| ARCH-047 | The commons area is strictly limited | MUST | partial |
| ARCH-048 | No context-level application package | MUST | full |
| ARCH-049 | One aggregate root per aggregate module | MUST | partial |
| ARCH-050 | Declared context dependency graph | MUST | full |
| ARCH-052 | Read layer does not import the write side | MUST | full |
| ARCH-054 | Domain services for an aggregate live in a services/ directory | SHOULD | partial |
| ARCH-055 | Every Python package directory has an __init__.py | SHOULD | full |
| ARCH-056 | An entrypoint file serves at most one aggregate module | SHOULD | partial |
| ARCH-059 | bootstrap/ wires adapters, it does not define them | SHOULD | full |

### Rule reference

#### ARCH-001 — Domain does not depend on adapters
- **Level:** MUST · **Automation:** full · **Tier:** core · **Category:** dependencies
- **Validation:** `import-linter` — layered contract; domain is the innermost layer
- **Description:** No module under a context's domain/ package may import from that context's adapters/ package or from commons/adapters/.
- **Rationale:** Inverting this dependency (DIP) lets the core be tested without a database and lets the store be swapped without touching business rules.
- **Correct:**
  ```
  # sales/orders/domain/model/ports.py
  class OrderRepository(ABC):
      @abstractmethod
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
  from sales.orders.application.order import OrderService
  ```

#### ARCH-003 — Domain does not depend on frameworks
- **Level:** MUST · **Automation:** full · **Tier:** core · **Category:** dependencies
- **Validation:** `ast-checker` — forbidden imports in domain/ and commons/, excluding commons/adapters/; `from pydantic import <name>` is permitted only for names on the scalar-validator allowlist, `import pydantic` (bare) is never permitted
- **Description:** No module under a context's domain/ package (or a project's commons/, held to the same discipline) imports a web framework, an ORM, a DI container, or pydantic -- with two narrow, explicit exceptions. The first: a framework's own format-only scalar validators, imported by name. Today that allowlist is exactly `pydantic.EmailStr`, `pydantic.TypeAdapter` and `pydantic.ValidationError`, used only to validate a single field's string format in `__post_init__`, never to define a model, a schema, or anything with I/O. `import pydantic` (the bare form) stays banned even though names on the allowlist exist, because the bare form reaches `pydantic.BaseModel` through the module object; the same import line naming both an allowed and a banned symbol still fails. The second: a project's own `commons/adapters/`, when it exists (ARCH-047) -- it follows adapters/-layer discipline throughout, exactly like arch-commons' own `commons.adapters` or any context's own `adapters/`, so this rule does not apply to it at all, not even the scalar-validator allowlist (there is no reason to allowlist anything -- the whole module is exempt).
- **Rationale:** A framework-free domain stays unit-testable without a runtime and keeps vendor choices out of the business core -- reimplementing a well-known format (email, URL, phone) with a hand-rolled regex is not what that principle protects, and it trades one duplicated, under-tested validator per aggregate for one call into a library that already gets it right. The line stays exactly where the principle needs it: the domain may borrow a framework's scalar TYPE validator, never its MODELING machinery (no `BaseModel`, no `Field`, no framework runtime or I/O reaching the domain through the back door).
- **Correct:**
  ```
  # sales/orders/domain/model/value_objects.py
  from pydantic import EmailStr, TypeAdapter, ValidationError
  
  _EMAIL = TypeAdapter(EmailStr)
  
  @dataclass(frozen=True)
  class ContactInfo:
      email: EmailStr
  
      def __post_init__(self) -> None:
          if self.email:
              try:
                  _EMAIL.validate_python(self.email)
              except ValidationError as exc:
                  raise InvalidOrder(f"Email is not valid: {self.email}") from exc
  ```
- **Incorrect:**
  ```
  # sales/orders/domain/model/aggregate.py
  from pydantic import BaseModel        # modeling machinery, not a scalar validator
  from sqlalchemy.orm import Mapped
  
  # sales/orders/domain/model/value_objects.py
  import pydantic                        # bare import -- reaches BaseModel too,
                                          # banned even though EmailStr exists
  ```
- **Related:** ARCH-047

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
- **Rationale:** Orchestration names ports only; the concrete adapter is injected by the composition root and is never imported by the use case.
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
  # sales/entrypoints/web/order.py
  from sales.orders.application.order import OrderService
  ```
- **Incorrect:**
  ```
  # sales/orders/application/order.py
  from sales.entrypoints.web.order import parse_body
  ```

#### ARCH-007 — Application does not construct concrete adapters
- **Level:** MUST · **Automation:** partial · **Tier:** full · **Category:** dependencies
- **Validation:** `grimp` — import-graph assert; catches adapter classes imported from the adapters/ package, not an adapter class defined and instantiated within application/ itself
- **Description:** No module under a context's application/ package instantiates an adapter class such as SqlAlchemyOrderRepository(...) or HttpCreditGateway(...).
- **Rationale:** Constructing an adapter couples the use case to one technology choice and defeats dependency injection.
- **Correct:**
  ```
  # bootstrap/__init__.py
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
- **Validation:** `import-linter` — layered contract (import half); an adapter that doesn't inherit the port fails mypy and, if instantiated, raises TypeError for any unimplemented @abstractmethod -- both checked, not just reviewed
- **Description:** Every concrete adapter in a context's adapters/ package implements an abc.ABC declared in domain/model/ports.py or a colocated application abc.ABC; domain/ and application/ import only those abstractions.
- **Rationale:** The core names the contract it needs and adapters plug in behind it, so the store can be replaced without editing business rules.
- **Correct:**
  ```
  # sales/orders/adapters/order_repository.py
  class SqlAlchemyOrderRepository(OrderRepository):  # explicit, not duck-typed
      def get(self, order_id: OrderId) -> Order: ...
  ```
- **Incorrect:**
  ```
  # sales/orders/domain/services/order.py
  from sales.orders.adapters.order_repository import SqlAlchemyOrderRepository
  ```
- **Related:** ARCH-001, ARCH-042

#### ARCH-009 — Entrypoints obtain wired services from the composition root; never construct or call outbound adapters directly
- **Level:** MUST · **Automation:** partial · **Tier:** full · **Category:** dependencies
- **Validation:** `import-linter` — forbidden contract (import half); entrypoints calling persistence/session/http-client directly is a runtime fact the import graph cannot see
- **Description:** No module under a context's entrypoints/ package constructs an outbound adapter, imports bootstrap/, or calls persistence, sessions, or HTTP clients directly. It exposes its own small getter for the one service it needs, set once at startup by the composition root (main.py, the only module allowed to import bootstrap/ -- ARCH-017), and calls only that service.
- **Rationale:** An entrypoint that news up a repository or calls session.execute is untestable without transport and leaks wiring across the boundary.
- **Correct:**
  ```
  # sales/entrypoints/web/order.py
  _service: OrderService | None = None
  
  def configure(service: OrderService) -> None:
      global _service
      _service = service
  
  def get_order_service() -> OrderService:
      assert _service is not None, "configure() was not called at startup"
      return _service
  
  def create_order(body: CreateOrderBody, service: OrderService = Depends(get_order_service)):
      service.create_order(command)
  
  # sales/main.py -- the only module that imports bootstrap (ARCH-017)
  container = build_container()
  order.configure(container.order_service)
  ```
- **Incorrect:**
  ```
  # sales/entrypoints/web/order.py
  repo = SqlAlchemyOrderRepository(SqlAlchemyUnitOfWork())
  repo.save(order)
  ```

#### ARCH-010 — Entrypoints contain no business logic
- **Level:** SHOULD · **Automation:** partial · **Tier:** full · **Category:** dependencies
- **Validation:** `review` — PR checklist; does the handler decide anything about business meaning?
- **Description:** A module under a context's entrypoints/ package does not branch on business meaning; it translates the stimulus into a command, calls one service method, and maps the result or exception back to the transport.
- **Rationale:** Business rules in a controller are hidden from domain tests and cannot be reused by another entrypoint.
- **Correct:**
  ```
  # sales/entrypoints/web/order.py
  cmd = CreateOrder(customer_id=body.customer_id, lines=body.lines)
  return _to_response(service.create_order(cmd))
  ```
- **Incorrect:**
  ```
  # sales/entrypoints/web/order.py
  if order.total > customer.credit_limit:
      raise HTTPException(402)
  ```

#### ARCH-011 — Entrypoints call application services, not other entrypoints
- **Level:** MUST · **Automation:** full · **Tier:** full · **Category:** dependencies
- **Validation:** `import-linter` — forbidden contract; entrypoints/**/*.py -/-> entrypoints/**/*.py (recursive - covers web/, events/, crons/)
- **Description:** No module under a context's entrypoints/ package imports or calls another entrypoint module.
- **Rationale:** Chaining entrypoints hides a use case behind transport translation and duplicates orchestration.
- **Correct:**
  ```
  # sales/entrypoints/cli.py
  from sales.orders.application.order import OrderService
  # cli.py gets its own OrderService via its own configure()/getter,
  # set by main.py at startup -- never by importing web/order.py
  ```
- **Incorrect:**
  ```
  # sales/entrypoints/cli.py
  from sales.entrypoints.web.order import create_order_handler
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

#### ARCH-014 — commons imports nothing from any context
- **Level:** MUST · **Automation:** full · **Tier:** full · **Category:** dependencies
- **Validation:** `import-linter` — forbidden contract; commons -/-> contexts
- **Description:** No module under src/commons/ imports from any src/<context> package. A commons module may import other commons modules, including commons.types from the installed arch-commons package. When a context concept is needed in commons, the concept is promoted into commons rather than imported down from the context.
- **Rationale:** commons/ is upstream of every context; importing a context would invert the governance direction, couple all consumers and create a cycle. Keeping the dependency one-way is what lets any context use commons freely without asking which other context it might drag in.
- **Correct:**
  ```
  # commons/geo.py
  from commons.types.errors import DomainError
  ```
- **Incorrect:**
  ```
  # commons/geo.py
  from sales.orders.domain.model.aggregate import Order
  ```

#### ARCH-015 — commons/types imports nothing from contexts, application, adapters, or project commons modules
- **Level:** MUST · **Automation:** full · **Tier:** full · **Category:** dependencies
- **Validation:** `import-linter` — forbidden contract; commons.types -/-> everything above it
- **Description:** No module under commons/types/ imports from any context package, from any application/ or adapters/ package, or from a project-local commons module. The dependency inside commons/ is one-way: a project's commons.<module> may import commons.types, never the reverse.
- **Rationale:** commons/types is the dependency-free base importable by everyone including domain/; any upward import would create a cycle. It also ships from the installed arch-commons distribution, which cannot see a consuming project's own commons modules -- such an import would simply not resolve anywhere else.
- **Correct:**
  ```
  # commons/types/clock.py
  from abc import ABC, abstractmethod
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
- **Description:** Modules under commons/types/ hold only dependency-free technical primitives and ports, with no rule a business person would recognise. This applies to commons/types/ and commons/adapters/ -- the portions shipped by the installed arch-commons package -- and not to a project's own commons.<module> portions, which exist precisely to hold the project's transversal domain concepts.
- **Rationale:** arch-commons is installed by many projects, so a business policy placed there is invisible to the context that owns it and silently shared with every unrelated project that upgrades. A project's own commons module has neither problem: it ships with that project alone.
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
  # commons/types/pricing.py  (shipped by arch-commons)
  VAT_RATE = Decimal("0.21")  # a tax rule belongs to a context, or to the
                              # project's own commons/pricing.py -- never here
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
  class OrderRepository(ABC):
      @abstractmethod
      def get(self, order_id: OrderId) -> Order: ...
      @abstractmethod
      def add(self, order: Order) -> None: ...
  ```
- **Incorrect:**
  ```
  class OrderRepository(ABC):
      @abstractmethod
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
  class CreditCheckPort(ABC):
      @abstractmethod
      def has_credit(self, customer_id: CustomerId, amount: Money) -> bool: ...
  # bootstrap/ wires an adapter backed by billing's application service
  ```
- **Incorrect:**
  ```
  # sales/orders/application/order.py
  from billing.invoices.application.invoice import InvoiceService
  ```
- **Related:** ARCH-012, ARCH-045

#### ARCH-026 — External-provider dependencies sit behind a port
- **Level:** SHOULD · **Automation:** partial · **Tier:** full · **Category:** application
- **Validation:** `review` — PR checklist; is every external provider injected behind a port?
- **Description:** Any dependency on an external provider (email, payment, SMS, third-party API) is used through an abc.ABC injected into the use case, not by importing the vendor SDK into application/.
- **Rationale:** A port at the integration seam keeps the use case testable with a fake and lets the provider be swapped without touching orchestration.
- **Correct:**
  ```
  class PaymentGateway(ABC):
      @abstractmethod
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
  from abc import ABC, abstractmethod
  from collections.abc import Iterable
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

#### ARCH-038 — Domain objects are never mocked
- **Level:** SHOULD · **Automation:** partial · **Tier:** full · **Category:** testing
- **Validation:** `review` — PR checklist plus grep for Mock(spec=<domain type>) in tests
- **Description:** Tests never replace an aggregate, entity, domain value object, domain service, or commons value object with a mock or stub; they exercise the real object.
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
- **Description:** A port (abc.ABC) is placed by the three-homes rule (generic technical ports in commons/types/, domain-vocabulary contracts in domain/model/ports.py, non-domain outbound contracts colocated in the use-case module), and there is no application/ports.py until a context has 3+ application ports shared across use-case modules.
- **Rationale:** Keeping domain/model/ports.py a faithful list of domain concepts keeps integration-contract churn out of the stable domain file.
- **Correct:**
  ```
  # commons/types/clock.py                    -> Clock
  # sales/orders/domain/model/ports.py        -> OrderRepository
  # sales/orders/application/order.py -> class OrderNotifier(ABC): ...
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
  class CreditCheckPort(ABC):
      @abstractmethod
      def has_credit(self, customer_id: CustomerId, amount: Money) -> bool: ...
  ```
- **Incorrect:**
  ```
  # sales/orders/adapters/credit_gateway.py
  from billing.invoices.application.invoice import InvoiceService  # calls 8 of 20 methods
  ```
- **Related:** ARCH-012, ARCH-025

#### ARCH-046 — Aggregate module isolation
- **Level:** MUST · **Automation:** full · **Tier:** core · **Category:** structure
- **Validation:** `import-linter` — forbidden contract between sibling modules' application and adapters
- **Description:** An aggregate module does not import another aggregate module's application/ or adapters/ package. References between aggregates are by ID, and those ID types live in commons/ids.py.
- **Rationale:** Aggregate modules are consistency boundaries. Reaching into a sibling's service or repository re-couples them and makes the one-transaction-one-aggregate rule unenforceable.
- **Correct:**
  ```
  # sales/orders/domain/model/aggregate.py
  from commons.ids import UserId
  class Order:
      customer_id: UserId
  ```
- **Incorrect:**
  ```
  # sales/orders/application/order.py
  from sales.users.application.user import UserService
  ```
- **Related:** ARCH-020, ARCH-021

#### ARCH-047 — The commons area is strictly limited
- **Level:** MUST · **Automation:** partial · **Tier:** full · **Category:** structure
- **Validation:** `ast-checker` — no class named *Service/*Repository outside commons/services.py or commons/adapters/; no aggregate roots outside commons/adapters/; commons/services.py classes must not mutate their own state; commons/adapters/ is skipped entirely by both checks
- **Description:** src/commons/ holds only ID types, value objects, enumerations and reference catalogues, and domain services spanning aggregates — plus one further carve-out, commons/adapters/: framework-bound technical adapters used by more than one context, not (yet) proposed upstream into arch-commons (Section 8.1), or specific enough to this project that upstreaming never applies. Domain services spanning aggregates live specifically in commons/services.py — the one top-level file in commons/ exempt from the *Service/*Repository name-suffix ban, since it is the standard's own documented home for them; commons/services.py classes still may not mutate their own state. commons/adapters/, by contrast, follows adapters/ -layer discipline throughout, exactly like arch-commons' own commons.adapters or any context's own adapters/: framework imports are allowed (ARCH-003 does not apply there), the name-suffix ban does not apply, and mutation is expected. Every other file directly in commons/ keeps the full name-suffix ban and framework-free discipline. commons/ never holds an aggregate root, a repository, or an application service, and commons/adapters/ never holds anything but a technical adapter implementation — no business logic, no aggregate, no port definition (a port lives in commons/types/, upstream, per the three-homes rule, ARCH-042).
- **Rationale:** commons/ is visible to every context, so without a narrow admission test it becomes the junk drawer that couples the whole project together. Unlike commons/types/ (ARCH-016) it may carry business meaning — that is what it is for — but business meaning is not licence to put behaviour-owning objects there. Naming each legitimate exception explicitly (rather than banning *Service or framework imports outright everywhere in commons/) keeps every carve-out narrow instead of inviting the rest of commons/ to claim it. commons/adapters/ specifically exists because "propose it upstream into arch-commons" is the right long-term answer for a genuinely reusable technical primitive, but it is not a place to put code while a PR is pending, and some adapters (a request-scoped UnitOfWork tuned to one project's concurrency model, say) may never be generic enough to upstream at all. Without a documented, checked home, that code drifts into bootstrap/ instead — technically working, since bootstrap/ can import anything, but invisible to every context that could reuse it and indistinguishable from actual wiring code.
- **Correct:**
  ```
  # commons/ids.py
  @dataclass(frozen=True)
  class UserId:
      value: str
  
  # commons/geo.py — a transversal value object with real business meaning
  @dataclass(frozen=True)
  class Location:
      country: Country
      department: Department
      municipality: Municipality
  
  # commons/services.py — the documented carve-out
  class PricingService:
      def quote(self, order: Order) -> Money: ...
  
  # commons/adapters/unit_of_work.py — a project-owned technical adapter,
  # shared by every context, not (yet) proposed upstream
  class ScopedSqlAlchemyUnitOfWork(SqlAlchemyUnitOfWork):
      def __enter__(self) -> ScopedSqlAlchemyUnitOfWork: ...
  ```
- **Incorrect:**
  ```
  # commons/user_service.py — *Service outside services.py is still banned
  class UserService: ...
  
  # commons/order.py — an aggregate root never lives in commons/
  class Order: ...
  
  # commons/services.py — mutation is still banned even here
  class PricingService:
      def bump(self) -> None:
          self.calls += 1
  
  # bootstrap/unit_of_work.py — a reusable, cross-context technical adapter
  # defined in the composition root instead of commons/adapters/ (ARCH-059)
  class ScopedSqlAlchemyUnitOfWork(SqlAlchemyUnitOfWork): ...
  ```
- **Related:** ARCH-003, ARCH-034, ARCH-042, ARCH-055, ARCH-059

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
- **Description:** Repositories persist and retrieve aggregate roots. They are not general-purpose query interfaces. A query over one aggregate module's own data -- search, filter, sort, a paginated listing -- belongs to that module's own Finder (Section 2.5): a `Finder` ABC and its DTOs in `application/<aggregate>_finder.py`, implemented in `adapters/<aggregate>_finder.py` -- the same ABC/implementation split as the repository, and for the same reason (ARCH-009: an entrypoint never imports a module's `adapters/` directly). Not the repository, and not the context's read/ layer either -- that is for a query spanning 2+ aggregate modules, or a projection/report/dashboard.
- **Rationale:** A repository that grows report queries stops being a collection of roots, drags query pressure into the write model, and starts returning DTOs instead of aggregates. Naming the single-aggregate Finder explicitly (rather than pointing everything at read/) matters just as much: read/ exists because some queries span aggregate modules, and promoting a single-aggregate listing there anyway buys nothing while duplicating that aggregate's row shape in a file nobody else needed.
- **Correct:**
  ```
  class OrderRepository(ABC):
      @abstractmethod
      def get(self, order_id: OrderId) -> Order: ...
      @abstractmethod
      def add(self, order: Order) -> None: ...
  
  # sales/orders/application/order_finder.py -- the port, entrypoint-importable
  class OrderFinder(ABC):
      @abstractmethod
      def list_orders(self, query: ListOrders) -> Page[OrderListItem]: ...
  
  # sales/orders/adapters/order_finder.py -- the implementation, wired by
  # bootstrap/ like the repository, never imported by an entrypoint directly
  class InMemoryOrderFinder(OrderFinder):
      def list_orders(self, query: ListOrders) -> Page[OrderListItem]: ...
  ```
- **Incorrect:**
  ```
  class OrderRepository(ABC):
      @abstractmethod
      def find_premium_customers_with_overdue_invoices(self) -> list[ReportRow]: ...
  
  # sales/orders/entrypoints/web/order.py -- reaches into adapters/ directly,
  # the exact thing splitting the Finder into a port avoids (ARCH-009)
  from sales.orders.adapters.order_finder import InMemoryOrderFinder
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
- **Description:** An aggregate module's domain services live in domain/services/, one file per service - not a single domain/services.py file. A single service is named after the aggregate (order.py for the Order aggregate); 2+ services each get a descriptive name instead. This does not apply to commons/services.py (ARCH-047), the separate project-level home for services spanning aggregates.
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
- **Validation:** `ast-checker` — filesystem check - every directory under src/ holding a .py file has __init__.py, except src/commons/ itself, which must not have one
- **Description:** Every directory under src/ that contains a .py file (directly or in a subdirectory) has an __init__.py, including empty ones. Implicit namespace packages (PEP 420) are not used. The exceptions are src/commons/ itself and, if it exists, src/commons/adapters/ — neither MUST have one: each is a PEP 420 namespace portion that merges with the matching portion the installed arch-commons distribution ships (commons/ with commons.types/commons.adapters as a whole; commons/adapters/ with arch-commons' own commons/adapters/ specifically, ARCH-047). Every other directory nested under src/commons/, including subdirectories of commons/adapters/ itself, follows the normal rule and does have an __init__.py.
- **Rationale:** An explicit __init__.py marks a directory as a package on purpose, rather than by the accident of holding a .py file; it also avoids the edge cases implicit namespace packages create for some tooling and IDEs. A missing one is easy to overlook when scaffolding a module by hand. commons/ and commons/adapters/ are the deliberate exceptions: arch-commons ships commons.types and commons.adapters while the project supplies its own commons.<module> portions and, when it has one, its own framework-bound adapters alongside arch-commons' commons.adapters -- and a regular package on either side of either merge point would shadow the other outright rather than merge with it.
- **Correct:**
  ```
  sales/orders/domain/model/__init__.py   # empty, present
  sales/orders/domain/model/aggregate.py
  
  commons/geo.py                          # no commons/__init__.py -- namespace portion
  commons/ids/__init__.py                 # nested dirs still have one
  commons/adapters/unit_of_work.py        # no commons/adapters/__init__.py either
  ```
- **Incorrect:**
  ```
  sales/orders/domain/model/aggregate.py  # no __init__.py alongside it
  
  commons/__init__.py                     # shadows the installed arch-commons
  commons/adapters/__init__.py            # shadows arch-commons' own commons/adapters/
  ```

#### ARCH-056 — An entrypoint file serves at most one aggregate module
- **Level:** SHOULD · **Automation:** partial · **Tier:** full · **Category:** structure
- **Validation:** `ast-checker` — an entrypoints/ file importing from 2+ aggregate modules' packages in the same context is flagged; only applies to contexts with 2+ modules
- **Description:** entrypoints/ groups by transport kind (web/, events/, crons/), and within each kind, one file per aggregate module (or per concern, for events/crons where a single file's job doesn't map cleanly to one aggregate name). A file that imports from two different aggregate modules' packages under the same context is doing more than one aggregate's job.
- **Rationale:** Web routes typically split naturally, one file per resource. Event consumers and cron jobs are better named for what they do than forced into an aggregate-name pattern, but the ownership rule still holds: a handler that reaches into two aggregates hides a cross-aggregate flow inside transport code instead of an explicit part of the design (Section 3.6), and is untestable without two aggregates' worth of setup.
- **Correct:**
  ```
  # sales/entrypoints/web/order.py
  from sales.orders.application.order import OrderService
  ```
- **Incorrect:**
  ```
  # sales/entrypoints/web/order.py
  from sales.orders.application.order import OrderService
  from sales.customers.application.customer import CustomerService
  ```

#### ARCH-057 — HTTP entrypoints centralize response shaping in the composition root
- **Level:** SHOULD · **Automation:** manual · **Tier:** full · **Category:** dependencies
- **Validation:** `review` — PR checklist; does any handler build the envelope/error shape itself instead of returning its plain model?
- **Description:** A web entrypoint context applies cross-cutting response shaping -- a uniform success/error envelope, standard error formatting -- through one mechanism registered once by the composition root (e.g. ASGI middleware set up in main.py), not by each handler building it by hand. The envelope's exact shape is a project decision, not something this rule mandates; what MUST be centralized is the mechanism.
- **Rationale:** Repeating envelope or error-formatting logic in every handler drifts inconsistent over time and puts a transport-format decision inside business-translation code; one composition-root-registered wrapper keeps the shape uniform and handlers focused on stimulus -> command -> service call (ARCH-010).
- **Correct:**
  ```
  # bootstrap/envelope.py
  class EnvelopeMiddleware(BaseHTTPMiddleware):
      async def dispatch(self, request, call_next):
          response = await call_next(request)
          ...  # reshape into {"payload": ..., "errors": ...}
  
  # main.py -- registered once
  app.add_middleware(EnvelopeMiddleware)
  
  # sales/entrypoints/web/order.py -- handler returns its plain model
  def create_order(...) -> OrderResponse: ...
  ```
- **Incorrect:**
  ```
  # sales/entrypoints/web/order.py
  def create_order(...) -> dict:
      return {"payload": OrderResponse(...).model_dump(), "errors": None}
  ```
- **Related:** ARCH-009, ARCH-010

#### ARCH-058 — A test file's directory mirrors the source it tests
- **Level:** SHOULD · **Automation:** partial · **Tier:** full · **Category:** testing
- **Validation:** `ast-checker` — a tests/**/test_*.py file whose imports resolve to exactly one src/ directory is flagged when it does not live at the mirrored tests/ path; a file with zero or 2+ resolved directories (fixtures, conftest, smoke/e2e) is not flagged
- **Description:** tests/ has the same directory shape as src/: a test file that imports from exactly one source directory (one aggregate's one layer, or one cross-cutting module) lives at the same path under tests/ instead of being flattened into tests/ with the layer or module folded into the filename. A test that legitimately spans more than one source directory -- a smoke test through the composition root, an end-to-end test through a real entrypoint -- is not flattened by this rule; there is no single mirrored path for it to move to.
- **Rationale:** A prefixed, flattened tests/ directory (test_client_aggregate.py, test_client_web.py, test_client_repository.py, ...) hides which layer each test belongs to and stops growing once two aggregates share a prefix word; tests/<context>/<module>/<layer>/test_<unit>.py answers "where does the test for this file live" the same way src/ answers "where does this file live" -- by walking the same path, not by parsing a filename.
- **Correct:**
  ```
  # tests/sales/orders/domain/model/test_aggregate.py
  from sales.orders.domain.model.aggregate import Order
  ```
- **Incorrect:**
  ```
  # tests/test_order_aggregate.py
  from sales.orders.domain.model.aggregate import Order
  ```
- **Related:** ARCH-040

#### ARCH-059 — bootstrap/ wires adapters, it does not define them
- **Level:** SHOULD · **Automation:** full · **Tier:** full · **Category:** structure
- **Validation:** `ast-checker` — a class defined under bootstrap/ is flagged when any base class is a name imported directly from commons.types or commons.adapters; a base class defined by indirection through another project module is not resolved
- **Description:** A class defined inside bootstrap/ MUST NOT directly subclass a port or adapter imported from commons.types or commons.adapters. Implementing a port is adapter-shaped code, and an adapter has a documented home already: a context's own <module>/adapters/ if it serves one aggregate module, or the project's own commons/adapters/ (ARCH-047) if it is framework-bound and shared across contexts. bootstrap/ constructs instances of adapters defined elsewhere and wires them into services; it does not define the classes themselves.
- **Rationale:** bootstrap/ can import anything (it is the one module ARCH-017 allows to reach across every layer), so nothing stops a class implementing a port from being defined there by accident -- it will even run correctly. What is lost is reuse and legibility: an adapter sitting in bootstrap/ is invisible to every context that could import it from commons/adapters/, and a reader cannot tell wiring code from adapter code without reading every class body. A documented, checked home removes the judgment call: a technical adapter used by more than one context is proposed upstream into arch-commons (Section 8.1) or, until that lands or if it never will, placed in commons/adapters/ -- never left in the composition root because that is where it happened to be written first.
- **Correct:**
  ```
  # commons/adapters/unit_of_work.py
  class ScopedSqlAlchemyUnitOfWork(SqlAlchemyUnitOfWork): ...
  
  # bootstrap/__init__.py
  from commons.adapters.unit_of_work import ScopedSqlAlchemyUnitOfWork
  
  def build_container() -> Container:
      uow = ScopedSqlAlchemyUnitOfWork(session_factory)
      ...
  ```
- **Incorrect:**
  ```
  # bootstrap/unit_of_work.py
  from commons.adapters.sqlalchemy_unit_of_work import SqlAlchemyUnitOfWork
  
  class ScopedSqlAlchemyUnitOfWork(SqlAlchemyUnitOfWork): ...  # ARCH-059: this
                                                                # is an adapter,
                                                                # not wiring
  ```
- **Related:** ARCH-017, ARCH-047

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

## 11.3 Directory structure

`tests/` has the same directory shape as `src/`: a test that imports from exactly
one source directory lives at the same path under `tests/`, not flattened at the
`tests/` root with the layer or module folded into the filename.
`tests/sales/orders/domain/model/test_aggregate.py`, not
`tests/test_order_aggregate.py`. A test that legitimately spans more than one
source directory -- a smoke test through the composition root, an end-to-end test
through a real entrypoint -- has no single mirrored path and is not flattened by
this rule; it stays wherever it already sits (typically `tests/` root, named
`test_<aggregate>_smoke.py` or similar). Shared test infrastructure that is not
itself a test -- `conftest.py`, builders, in-memory doubles, fixtures -- is
unaffected; only `test_*.py` files are placed by this rule. (ARCH-058)

## 11.4 Mock / do not mock

- **Never mock:** domain objects (aggregates, VOs, services), the code under test,
  `commons` VOs. (ARCH-038)
- **Use in-memory fakes, not mocks:** repositories (`InMemoryOrderRepository` over a
  dict, bound to an `InMemoryUnitOfWork`), `EventBus` (`RecordingEventBus`), `Clock`
  (`FixedClock`). The same contract test runs against the fake and the real adapter -
  the fake cannot lie. (ARCH-039)
- **Mock only in adapter tests:** the third party's SDK when testing your adapter - and
  even then prefer a fake server, VCR, or testcontainer.
- **Rule of thumb:** an application test with more than 1 to 2 mocks means the service
  does too much or dependencies are not properly injected.

## 11.5 Per-layer guidance

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

## 11.6 Coverage as a rule

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
| Shared module as junk drawer | global coupling, contexts cannot evolve independently | strict `commons` admission rules (ARCH-014/047); duplicate by default |
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
| AST structural rules | custom `ast` checker shipped with the standard | 023, 031, 018, 019, 030 (service size: methods/lines/params), 040, 041 (promotion thresholds), 043 (envelope shape), 058 (tests/ mirrors src/) | CI + pytest |
| ADR waiver expiry | validator date check over `docs/adr/` | 021*, 036, any waived MUST | CI |
| Package boundaries with a public API | tach (`tach.toml`) | 012, 042, 045 | CI |
| Event schema / contract testing | pydantic/jsonschema export + consumer fixtures; optionally Pact | 024, 043, 044 | CI (producer & consumer) |
| Test taxonomy | pytest markers + a conftest rule forbidding adapter imports in domain tests | 038 | CI |
| Coverage gates per layer | coverage.py with per-path thresholds | Section 11.6 | CI |
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
| `src/commons/` | anything beyond IDs, VOs, enums/catalogues, and cross-aggregate domain services | ARCH-047 violation, or the aggregates are wrongly separated. |
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
