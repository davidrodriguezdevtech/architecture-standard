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
- **Ports.** `typing.Protocol` (structural typing; adapters do not inherit). Three
  homes: `commons/types/` (generic technical protocols), `domain/model/ports.py`
  (domain vocabulary), and colocated in the use-case module (non-domain outbound).
  There is no `application/ports.py` by default.
- **Persistence.** The normative contract (the `UnitOfWork` Protocol, repository ports,
  translation living in `infrastructure/`) is store-agnostic. SQLAlchemy is the shipped
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
- **Read models.** Domain-derived projections live in `domain/model/projections.py`.
  Query, dashboard, and presentation read models live outside the domain, introduced
  when complexity justifies them.
- **Mapping (domain to DTO).** Manual mapping for domain-facing boundaries. Libraries
  are allowed for mechanical mapping at infrastructure and transport boundaries.
- **Cross-context communication.** Synchronous by default, contract-mediated, wired in
  `bootstrap/`, with zero imports between contexts. Asynchronous integration events
  when the use case explicitly tolerates eventual consistency.
- **Process wiring.** `main.py` is the process entrypoint. `bootstrap/` is the
  Composition Root.

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
