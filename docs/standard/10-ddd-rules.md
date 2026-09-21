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
