# 2. Structure

## 2.1 Canonical tree

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
│   │   │   │   ├── ports.py       # domain-vocabulary ports only (Protocol): repositories,
│   │   │   │   │                  #   domain-service providers. Generic tech Protocols
│   │   │   │   │                  #   (Clock, UnitOfWork, EventBus, IdGenerator) → commons/types/.
│   │   │   │   │                  #   Non-domain outbound contracts → colocated in application/.
│   │   │   │   ├── projections.py # domain-derived read projections (when they exist)
│   │   │   │   └── exceptions.py  # concrete domain exceptions (subclass commons DomainError)
│   │   │   ├── services.py        # domain services (optional; only if needed)
│   │   │   └── specifications.py  # specifications / policies (optional)
│   │   ├── application/
│   │   │   ├── <context>_service.py   # the general service: one method per use case,
│   │   │   │                          #   command objects + colocated Protocols.
│   │   │   │                          #   Split to a second module only when a guardrail triggers.
│   │   │   └── integration_events.py  # integration events this context publishes + mapping
│   │   └── infrastructure/
│   │       ├── <adapter>.py       # one module per outbound adapter
│   │       ├── mapping.py         # aggregate <-> stored-form translation (mechanism per store;
│   │       │                      #   SQLAlchemy: Tables + map_imperatively, configure_mappings())
│   │       └── <aggregate>_repository.py  # thin repo impl; takes the UnitOfWork as a param
│   ├── commons/
│   │   ├── types/                 # dependency-free technical primitives + Protocols. Importable by ALL
│   │   │   ├── ids.py             # EntityId base, IdGenerator Protocol
│   │   │   ├── pagination.py
│   │   │   ├── errors.py          # DomainError, ApplicationError base classes
│   │   │   ├── clock.py           # Clock Protocol
│   │   │   ├── event_bus.py       # EventBus Protocol
│   │   │   ├── envelope.py        # EventEnvelope: correlation_id, causation_id, occurred_at,
│   │   │   │                      #   event_type, event_version, payload (+ correlation contextvar)
│   │   │   └── unit_of_work.py    # UnitOfWork Protocol (store-agnostic: txn + event collection)
│   │   └── infrastructure/        # shared framework-bound technical implementations
│   │       ├── unit_of_work.py    # SqlAlchemyUnitOfWork + InMemoryUnitOfWork (reference impls)
│   │       └── outbox.py          # transactional outbox machinery
│   ├── shared_kernel/             # governed shared domain concepts (policy-bearing VOs).
│   │                              #   NOT scaffolded until genuinely needed.
│   └── bootstrap/                 # Composition Root: config, singletons, DI container,
│                                  #   service/UoW factories, router registration,
│                                  #   consumer startup
└── tests/
```

## 2.2 What goes where

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

## 2.3 The optional `module` level

When a single context legitimately owns two or more separable sub-areas, each with its
own aggregates, insert a module level:
`src/<context>/<module>/{domain,application,infrastructure}/`. Off by default.
