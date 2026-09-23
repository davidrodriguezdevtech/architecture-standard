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

**Value converters are a narrow exception to "no frameworks here."** A shared value
converter - a class that translates one value to and from its stored primitive, such
as a SQLAlchemy `TypeDecorator` mapping a `StrEnum` column to plain text - is used by
2+ aggregate modules' `adapters/mapping.py`, so by the "needed above one aggregate?"
test it belongs in `src/commons/`. It is not a `commons/adapters/` candidate: it
implements no port and subclasses no `commons.types` ABC (ARCH-008 - see 8.3), it
just happens to need the framework's own column-TYPE machinery to do its one job.
ARCH-003 carries a narrow, explicit allowlist for exactly this - the ORM's
`TypeDecorator`/`TypeEngine`/`Dialect` and built-in column-type primitives, imported
by name, never `Column`, `Table`, `Session`, or any other modeling/I/O construct.
Everything else about `commons/` discipline still applies to the file it lives in:
no business logic, no mutable state, no `*Service`/`*Repository` name (ARCH-047) -
only the framework-import ban is narrowly lifted, and only for the classes on that
allowlist.

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

It holds one thing only: a technical adapter implementation that **implements a port**
(ARCH-008), typically subclassing a `commons.types` ABC exactly like its upstream
counterparts do (`SqlAlchemyUnitOfWork` implementing `UnitOfWork`, and so on). It
never holds a port itself (a port lives in `commons/types/`, upstream, per the
three-homes rule, ARCH-042), an aggregate, or business logic of any kind (ARCH-047).

A framework-bound helper that does **not** implement a port - a value converter used
by `adapters/mapping.py` across aggregate modules, for instance - is not a
`commons/adapters/` candidate just because it is framework-bound. It goes in a plain
`commons/<concept>.py` instead, under ARCH-003's narrow value-converter exception
(8.2). "Framework-bound" and "implements a port" are independent axes; only their
conjunction belongs here.

`bootstrap/` constructs instances of adapters defined here (or anywhere else) and
wires them into services; it does not define adapter classes itself (ARCH-059) - a
class implementing a port belongs in an adapters/ directory, not the composition
root, whether or not it happens to work either way.
