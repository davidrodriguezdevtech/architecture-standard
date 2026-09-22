# 6. Application

## 6.1 Responsibility

Coordinate use cases for this module's aggregate: load it, invoke its business
method, persist via the Unit of Work, publish domain events, map domain to DTO,
control the transaction boundary, and enforce use-case-level authorization. No
business invariants - those are in the domain. (ARCH-005 to ARCH-007, ARCH-027,
ARCH-029)

## 6.2 Shape

One application service class per aggregate module; one public method per use case.
This follows from the 1:1 aggregate-module rule (Section 2.2): there is no "general
service that splits later," and no context-level application layer. The day-1 shape
is the steady-state shape. (ARCH-030, SHOULD)

```python
# sales/orders/application/order.py
@dataclass(frozen=True)
class CreateOrder:
    customer_id: str
    lines: tuple[OrderLineInput, ...]

class OrderNotifier(Protocol):           # colocated non-domain outbound contract
    def order_placed(self, order_id: OrderId) -> None: ...

class OrderService:
    def __init__(
        self,
        uow: UnitOfWork,
        orders: OrderRepository,        # injected already bound to `uow`
        bus: EventBus,
        notifier: OrderNotifier,
    ) -> None: ...

    def create_order(self, command: CreateOrder) -> OrderId:
        with self._uow:
            order = Order.place(CustomerId(command.customer_id), command.lines)
            self._orders.add(order)
            self._uow.commit()
        self._bus.publish_all(self._uow.collect_new_events())
        return order.id

    def cancel_order(self, command: CancelOrder) -> None: ...
    def add_item(self, command: AddItemToOrder) -> None: ...
```

Guardrails (ARCH-030):

- One method equals one use case equals one transaction, on this module's aggregate.
- Zero business rules in the service. An `if` about business meaning moves to the
  domain.
- A method that needs to change a second aggregate is a design signal, not a licence
  to reach across - see Section 3.6.
- The checker warns past roughly 7 public methods, 200 lines, or 5 constructor
  parameters. At that size the aggregate itself is usually doing too much - look at
  the aggregate before splitting the service.
- Naming follows the aggregate: `OrderService` in `orders/`, `UserService` in
  `users/`.
- Command objects are frozen dataclasses; they may live in the same module as the
  service.

## 6.3 Ports

Inbound versus outbound:

- **Domain ports** (repositories, domain-service providers) are indispensable. DIP
  requires them - the core must not name adapters. MUST.
- **The application inbound port** is the use-case / service class itself, exposed to
  entrypoints. Its public methods are the port. There is no separate interface.
- **Application outbound ports** that are not domain vocabulary (`EmailSender`,
  `PaymentGateway`, cross-context gateways): the explicit `Protocol` is optional
  (SHOULD) - write it when the seam benefits from being explicit (testing,
  type-checking, multiple implementations, agent-readability), and skip it
  (duck-typed injection) for a trivial single-implementation dependency. Injection is
  never optional: the concrete adapter is built in `providers.py` and injected;
  `application/` never imports it.

Three homes, one rule each:

| Home | What lives here | The test |
|---|---|---|
| `commons/types/` | generic technical Protocols: `Clock`, `UnitOfWork`, `EventBus`, `IdGenerator` | dependency-free, no business meaning, reusable in any project |
| `domain/model/ports.py` | domain-vocabulary contracts: repositories, domain-service providers (`PricingPolicyProvider`) | you would mention it describing the business; a domain object or the repository abstraction needs it |
| a `Protocol` colocated in the use-case module | non-domain outbound contracts the orchestration needs: `EmailSender`, `PaymentGateway`, cross-context gateways (`CreditCheckPort`) | only `application/` uses it; it is integration plumbing, not domain language |

- No `application/ports.py` file by default - colocated `Protocol`s are the mechanism.
  (ARCH-042, SHOULD)
- Promote to `application/ports.py` only when a context has 3+ application ports
  shared across multiple use-case modules (Progressive Structure, Section 15).
- Rationale: this keeps `domain/model/ports.py` a faithful list of domain concepts and
  keeps integration-contract churn out of the stable domain file.

## 6.4 Integration events - conditional, not in the default shape

There is no `integration_events.py` in the canonical tree. Until this context
publishes to another context asynchronously, all events are domain events in their
aggregate module's `domain/model/events.py`.

When the promotion rule in Section 3.4 fires - another context starts consuming one
of this context's events - the promoted event moves to a dedicated module at the
context root, gains a versioned schema in the events catalog, and every publish wraps
it in the `commons/` `EventEnvelope` (correlation and causation IDs, type, version) so
async flows stay traceable (ARCH-043). Consumers never import that module; they see
serialized envelopes only.

## 6.5 Domain logic versus application orchestration

| Domain logic | Application orchestration |
|---|---|
| "An order cannot exceed the customer's credit limit" | "Load the order, add the item, save, publish `ItemAdded`" |
| "A shipped order cannot be cancelled" | "Begin transaction, on failure roll back and publish nothing" |
| "Discount = policy applied to line totals" | "Map the HTTP body to a command; map the aggregate to a response DTO" |
