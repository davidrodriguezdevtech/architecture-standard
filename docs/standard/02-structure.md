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
│   │   └── services.py               #   domain services spanning aggregates (rare)
│   └── bootstrap/                    # Composition Root: config, singletons, DI container,
│                                     #   service/UoW factories, router registration,
│                                     #   consumer startup
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
| A shared framework-bound technical implementation | the `arch-commons` package, `commons.adapters` (propose upstream) |
| A domain concept shared by 2+ contexts, with business policy | `src/commons/<concept>.py` |
| Wiring / config / DI | `bootstrap/` |

## 2.4 There is no context-level `application/`

DDD has no "application service of the context" - application services are per use
case and belong with the model they coordinate. Cross-aggregate flow is handled by the
rules in Section 3.6, not by a coordinating layer.

There is no context-level code area at all. Anything above one aggregate - whether it
crosses two aggregates of one context or two contexts - goes to `src/commons/`, which
is strictly limited to the things in the table above: ID types, value objects, enums
and reference catalogues, and domain services spanning aggregates. It never holds an
aggregate root, a repository, or an application service. (ARCH-047)

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
