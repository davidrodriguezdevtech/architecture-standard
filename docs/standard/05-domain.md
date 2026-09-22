# 5. Domain

## 5.1 Contents and dependencies

`domain/` contains: `model/` (aggregates, entities, value objects, domain events,
ports, projections, exceptions), `services/` (one file per domain service;
`service.py` when there's only one), and `specifications.py`.

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
