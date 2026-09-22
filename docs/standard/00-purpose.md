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
  `application/`. `<context>/shared/` is the only context-level code area, and it is
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
