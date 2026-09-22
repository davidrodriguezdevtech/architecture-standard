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
`__init__.py` (ARCH-055).

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
`arch-commons`. Until it is accepted it lives in that project's own `commons/`,
clearly marked.

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
