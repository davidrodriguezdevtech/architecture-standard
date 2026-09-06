# 8. commons/ and shared_kernel/

## 8.1 Two technical tiers

| | `commons/types/` | `commons/infrastructure/` |
|---|---|---|
| Content | dependency-free technical primitives, protocols | framework-bound shared technical implementations |
| Examples | `Result`-free error bases, `EntityId`, `Pagination`, `Clock` / `EventBus` / `IdGenerator` / `UnitOfWork` Protocols | `SqlAlchemyUnitOfWork` / `InMemoryUnitOfWork` (reference impls: session, txn, event collection), outbox machinery |
| Importable by | everyone, including `domain/` | only `infrastructure/`, `entrypoints/`, `bootstrap/`, tests |
| Forbidden | any business meaning, any framework import | - |

Rules: ARCH-015 (`commons.types` imports nothing from
contexts/application/infrastructure/shared_kernel), ARCH-016 (`commons.types` has no
business logic), ARCH-034 (`commons.infrastructure` not imported by
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
