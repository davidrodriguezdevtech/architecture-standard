# 11. Testing Strategy

## 11.1 Pyramid

| Level | Tests | Dependencies | Speed |
|---|---|---|---|
| Domain | aggregates, VOs, services, specs, policies - invariants and rules | none, real objects | us |
| Application | service methods (use cases) - orchestration, transaction, events published | real domain + in-memory fakes of the ports | ms |
| Adapter / integration | each adapter against its real technology | real DB/broker (testcontainers) | s |
| Contract | integration event schema, producer to consumers | schema fixtures | ms |
| End-to-end | full flow through a real entrypoint | context stack | s+ |

## 11.2 Naming

`given_<state>__when_<action>__then_<result>` - a double underscore separates the three
parts. Example:
`given_shipped_order__when_add_item__then_raises_order_already_shipped`. (ARCH-040)

## 11.3 Mock / do not mock

- **Never mock:** domain objects (aggregates, VOs, services), the code under test,
  `shared_kernel` VOs. (ARCH-038)
- **Use in-memory fakes, not mocks:** repositories (`InMemoryOrderRepository` over a
  dict, bound to an `InMemoryUnitOfWork`), `EventBus` (`RecordingEventBus`), `Clock`
  (`FixedClock`). The same contract test runs against the fake and the real adapter -
  the fake cannot lie. (ARCH-039)
- **Mock only in adapter tests:** the third party's SDK when testing your adapter - and
  even then prefer a fake server, VCR, or testcontainer.
- **Rule of thumb:** an application test with more than 1 to 2 mocks means the service
  does too much or dependencies are not properly injected.

## 11.4 Per-layer guidance

- **Aggregates:** pure objects, never through the repository. Assert new state, emitted
  domain events, and that invalid cases raise the correct domain exception. One test
  per rule, not per method. Domain tests run without the store's mapping or translation
  configuration - an autouse fixture ensures aggregate classes stay uninstrumented
  (with the SQLAlchemy reference impl, `configure_mappings()` is not called).
- **Application services:** real domain + fakes. Assert the right aggregate was loaded,
  the business method was called, persistence happened, the expected integration events
  were published, and the transaction commits or rolls back. Do not re-test domain
  rules here. Test rollback explicitly.
- **Adapters:** repository round-trip (`add` -> `get` -> full equality) plus
  specification-to-query translation; publisher and consumer against a real broker,
  with the serialized message matching the Published Language schema.
- **Contract tests:** producer - every emitted event validates against its published
  schema; consumer - inbound fixtures validate against the producer schema
  (consumer-driven: removing a field the consumer uses breaks the build). A schema
  change means a new event version, never an in-place edit.

## 11.5 Coverage as a rule

Domain above 90% (pure, cheap). Application: every use case with happy path, rollback,
and events. Adapters: round-trip plus error translation. E2E: critical business flows
only.
