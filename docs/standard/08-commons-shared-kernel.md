# 8. commons/ and shared_kernel/

## 8.1 `arch-commons` - a separately versioned package

`commons/` is not vendored into each project. It is published as `arch-commons` and
declared as a dependency, so a fix or a new primitive reaches every project that
upgrades instead of drifting into N divergent copies. This is what makes the standard
usable as the base of many repositories rather than a one-off scaffold.

| | `commons.types` | `commons.infrastructure` |
|---|---|---|
| Content | dependency-free technical primitives and Protocols | framework-bound shared implementations |
| Examples | `DomainError`/`ApplicationError` bases, `EntityId`, `Pagination`, `Clock` / `EventBus` / `IdGenerator` / `UnitOfWork` Protocols | `SqlAlchemyUnitOfWork`, `InMemoryUnitOfWork`, outbox machinery |
| Importable by | everyone, including `domain/` | only `infrastructure/`, `entrypoints/`, `bootstrap/`, tests |
| Forbidden | any business meaning, any framework import | - |

**Governance.** `arch-commons` follows semver, with the same compatibility policy as
the standard itself (Section 16.3): a breaking change to `commons.types` is a major
bump and is announced with migration notes. Adding a primitive is a minor. Consuming
projects pin a version and upgrade deliberately.

**Contributing upward.** A technical primitive that a project invents locally, and
that a second project would want, does not get copied - it is proposed upstream into
`arch-commons`. Until it is accepted it lives in that project, clearly marked.

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
