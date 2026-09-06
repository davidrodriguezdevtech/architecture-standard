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

## 3.4 Published Language

The vocabulary of integration events is a shared contract expressed as schema
(JSON Schema / Avro / Pydantic export) in an events catalog - never as importable
classes. Every integration event has a published, versioned schema. (ARCH-024, ARCH-044)

## 3.5 Extraction path

Because infrastructure is behind ports and cross-context contracts are already
explicit, extracting a context to its own service means: replace the in-process
gateway adapter with an HTTP client, and replace the in-process bus with a real broker.
`domain/` and `application/` are untouched.
