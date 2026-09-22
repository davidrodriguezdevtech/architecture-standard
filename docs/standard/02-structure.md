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
