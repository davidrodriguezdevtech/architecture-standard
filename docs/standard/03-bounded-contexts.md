# 3. Bounded Contexts

## 3.1 Rules

- The first level of `src/` is bounded contexts. Each context owns its own model,
  language, and rules.
- A context MUST NOT import another context's internals (`domain/`, `application/`,
  `infrastructure/`). Zero imports between contexts. (ARCH-012)
- Contracts (ports, event schemas, boundary DTOs) are defined as if the contexts were
  physically separable.
- No dependency cycles between contexts. (ARCH-013)

## 3.2 Communication - decision order

| Situation | Mechanism |
|---|---|
| Consumer needs data/decision from another context now, and staleness is unacceptable | Synchronous, contract-mediated. The consumer declares its own consumer-driven port; `bootstrap/` wires an adapter backed by the other context's application service; the consumer's `infrastructure/<x>_gateway.py` implements the port and does the ACL. Zero imports between contexts. |
| The use case explicitly tolerates eventual consistency; or fan-out to many consumers; or crossing a future service boundary | Asynchronous integration events. The producer publishes a versioned, serialized event; each consumer has an ACL translating the raw message to its own model. Published via transactional outbox when delivery must be guaranteed. |
| Producer needs a consumer to do something | Send a command, not an event. Events are facts (past tense); they never oblige a handler. |
| A concept looks shared but means different things in each context | Duplicate. Each context models its own. Sharing is the exception. |

## 3.3 Anti-Corruption Layer

Every inbound translation from another context (a synchronous response or an
asynchronous message) passes through an ACL in the consumer's `infrastructure/`. The
ACL is the only place that knows the other context's contract shape; the rest of the
consumer sees only its own model.

## 3.4 Published Language - conditional

Integration events do not exist by default. Until a context actually publishes to
another context asynchronously, every event is a domain event living in its aggregate
module's `domain/model/events.py`. Introducing an integration-event module before
there is a consumer is speculative.

The promotion rule: a domain event that starts being consumed by another context stops
being internal and becomes a contract. At that moment it is promoted out to a
dedicated module and acquires a versioned schema in an events catalog - expressed as
schema (JSON Schema / Avro / Pydantic export), never as an importable class. From then
on, changing it is a contract change.

Without this rule, someone subscribes to an internal domain event and every subsequent
refactor silently becomes a breaking change for another team. (ARCH-024, ARCH-044 -
both conditional MUSTs, applying once a context publishes integration events.)

## 3.5 Extraction path

Because infrastructure is behind ports and cross-context contracts are already
explicit, extracting a context to its own service means: replace the in-process
gateway adapter with an HTTP client, and replace the in-process bus with a real broker.
`domain/` and `application/` are untouched.

## 3.6 Cross-aggregate flow within a context

A use case that spans two aggregates cannot be one transaction (Section 5.3), so there
is nothing atomic to orchestrate. The rules, in order:

1. Default - choreography by domain events. `users` emits `UserRegistered`;
   `entrypoints/events.py` consumes it and makes one call to
   `subscriptions/application/subscription_service.py`. One service call per
   entrypoint handler. This is an inbound adapter doing its job, not orchestration.
2. Never sequence multi-step flow inside an entrypoint handler. Sequencing and
   compensation are logic: they would only be testable through the transport, they get
   rewritten per transport, and it is the Fat Controller anti-pattern (Section 12). It
   also breaks the hexagonal criterion that the application must be drivable from a
   test with no adapter attached.
3. Synchronous multi-aggregate requests (an endpoint that must return a result derived
   from two aggregates) have two sanctioned answers: return `202 Accepted` plus a
   resource to poll, or make only the first aggregate's write synchronous and return
   its id, letting the rest happen asynchronously.
4. Diagnostic - this is the most valuable of the four. If atomicity across two
   aggregates is frequently needed, the aggregate boundaries are drawn wrong. Redraw
   them before reaching for any coordinating construct.

There is deliberately no orchestration module in the canonical tree. If a genuine
long-running business process later demands one, the DDD pattern is a Process Manager
(stateful, tracks its own progress, lives in the application layer) - introduced as a
named exception with its own review, never as a general-purpose coordination layer.

## 3.7 Declared context dependency graph

Contexts do not import each other (ARCH-012), so no static import analysis can see a
cycle between them: a runtime cycle `sales -> billing -> sales` through
`bootstrap/`-wired gateways is invisible to every other check in this standard.

The fix is a declaration. `contexts.toml` at the project root lists, for each context,
the contexts it is allowed to depend on:

```toml
[contexts.sales]
depends_on = ["billing"]

[contexts.billing]
depends_on = []

[contexts.identity]
depends_on = []
```

- Every cross-context dependency wired in `bootstrap/` MUST correspond to a declared
  edge.
- The declared graph MUST be acyclic.
- Adding an edge is a deliberate, reviewable act - which is the real value: it turns
  "someone quietly wired B into A" into a diff.

(ARCH-050)
