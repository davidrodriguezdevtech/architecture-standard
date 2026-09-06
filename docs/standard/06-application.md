# 6. Application

## 6.1 Responsibility

Coordinate use cases: load an aggregate, invoke its business method, persist via the
Unit of Work, publish integration events, map domain to DTO, control the transaction
boundary, and enforce use-case-level authorization. No business invariants - those are
in the domain. (ARCH-005 to ARCH-007, ARCH-027, ARCH-029)

## 6.2 Shape

Default: one application service class per context; one public method per use case.
Additional service modules are introduced only when a guardrail below triggers - not
pre-split by capability. (ARCH-030, SHOULD)

```python
# application/order_service.py
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

Guardrails (ARCH-030) - a general service is the norm; these are the "when it hurts"
triggers to split into another module:

- One method equals one use case equals one transaction.
- Zero business rules in the service. An `if` about business meaning moves to the
  domain.
- Split when the class exceeds roughly 5 to 7 methods, or when constructor
  dependencies stop being cohesive (a method needs something the others do not), or
  when a context grows a second aggregate with its own distinct dependencies.
- The split line is whatever reduces coupling - usually per aggregate, sometimes
  command versus query, or a distinct capability (`OrderReturnsService`).
- `OrderService` is a fine name for the general service. It only becomes the God
  Service anti-pattern when it exceeds these guardrails and is not split.
- Command objects are frozen dataclasses; they may live in the same module as the
  service.

## 6.3 Ports

Inbound versus outbound:

- **Domain ports** (repositories, domain-service providers) are indispensable. DIP
  requires them - the core must not name infrastructure. MUST.
- **The application inbound port** is the use-case / service class itself, exposed to
  entrypoints. Its public methods are the port. There is no separate interface.
- **Application outbound ports** that are not domain vocabulary (`EmailSender`,
  `PaymentGateway`, cross-context gateways): the explicit `Protocol` is optional
  (SHOULD) - write it when the seam benefits from being explicit (testing,
  type-checking, multiple implementations, agent-readability), and skip it (duck-typed
  injection) for a trivial single-implementation dependency. Injection is never
  optional: the concrete adapter is built in `providers.py` and injected;
  `application/` never imports it.

Three homes, one rule each:

| Home | What lives here | The test |
|---|---|---|
| `commons/types/` | generic technical Protocols: `Clock`, `UnitOfWork`, `EventBus`, `IdGenerator` | dependency-free, no business meaning, reusable in any project |
| `domain/model/ports.py` | domain-vocabulary contracts: repositories, domain-service providers (`PricingPolicyProvider`) | you would mention it describing the business; a domain object or the repository abstraction needs it |
| a `Protocol` colocated in the use-case module | non-domain outbound contracts the orchestration needs: `EmailSender`, `PaymentGateway`, cross-context gateways (`CreditCheckPort`) | only `application/` uses it; it is integration plumbing, not domain language |

- No `application/ports.py` file by default - colocated `Protocol`s are the mechanism.
  (ARCH-042, SHOULD)
- Promote to `application/ports.py` only when a context has 3+ application ports shared
  across multiple use-case modules (Progressive Structure, Section 15).
- Rationale: this keeps `domain/model/ports.py` a faithful list of domain concepts and
  keeps integration-contract churn out of the stable domain file.

## 6.4 Integration events

`application/integration_events.py` defines the integration events this context
publishes (its outbound contract) and the mapping from domain events to integration
events to `EventBus`. Every publish wraps the event in the `commons/` `EventEnvelope`
(correlation and causation IDs, type, version) so async flows stay traceable
(ARCH-043). Consumers never import this module; they see serialized envelopes only.
(ARCH-024)

## 6.5 Domain logic versus application orchestration

| Domain logic | Application orchestration |
|---|---|
| "An order cannot exceed the customer's credit limit" | "Load the order, add the item, save, publish `ItemAdded`" |
| "A shipped order cannot be cancelled" | "Begin transaction, on failure roll back and publish nothing" |
| "Discount = policy applied to line totals" | "Map the HTTP body to a command; map the aggregate to a response DTO" |
