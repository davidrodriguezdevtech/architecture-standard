# 7. Infrastructure

## 7.1 Rules

- One module per outbound adapter. No sub-folders by type. A sub-folder is used only
  when a context accumulates many adapters of one kind (an exception, not the norm).
- Adapters implement ports declared in `domain/model/ports.py`; the core imports
  abstractions only. (ARCH-008)
- No Active Record. The aggregate has no persistence base class, decorator, or import,
  and no `save()`. Translation between the aggregate and its stored form lives entirely
  in `infrastructure/`, in whatever form the store needs. (ARCH-028)
- Adapters contain no business logic and make no orchestration decisions.
- `infrastructure/` MAY import `commons/infrastructure/`; `domain/` and `application/`
  MUST NOT. (ARCH-034)

## 7.2 Unit of Work and persistence

### Normative contract (store-agnostic)

`commons/types/unit_of_work.py` holds the `UnitOfWork` Protocol. It owns the
transaction and domain-event collection. It says nothing about a specific database.

```python
class UnitOfWork(Protocol):
    def __enter__(self) -> "UnitOfWork": ...
    def __exit__(self, *exc: object) -> None: ...      # rollback if commit() was not called
    def commit(self) -> None: ...
    def rollback(self) -> None: ...
    def track(self, aggregate: object) -> None: ...    # repositories call this on load/store
    def collect_new_events(self) -> Iterable[DomainEvent]: ...
```

- Repository ports in `domain/model/ports.py` are collection-style, root-level (`add`,
  `get`, `next_identity`, specification queries), and return aggregates - never rows or
  DTOs. (ARCH-022)
- Repositories receive the UoW and run against the store handle it exposes; they call
  `uow.track(aggregate)` on every load and store so events can be drained.
- Translation between the aggregate and its stored form lives entirely in
  `infrastructure/`, in whatever form the store needs. The aggregate has no persistence
  knowledge. (ARCH-028)
- One transaction modifies one aggregate (ARCH-021) - this keeps the UoW portable to
  stores without general multi-item transactions.
- There is no per-context UoW class. The application layer talks only to named
  repository ports, never to the UoW's store handle. (protects ARCH-022, ARCH-029)

### Reference implementation - SQLAlchemy

Shipped in `commons/infrastructure/` and the template.

- `SqlAlchemyUnitOfWork` owns a `Session`; `collect_new_events()` iterates
  `session.new | session.dirty | session.identity_map` and drains each aggregate
  root's pending events (so `track()` is effectively implicit for this store).
- Per context: `infrastructure/mapping.py` holds `Table` definitions plus
  `map_imperatively(Order, order_table, ...)`. There is no separate ORM model class and
  no manual mapper. Domain classes stay free of ORM base classes, decorators, and
  imports. `bootstrap/` calls each context's `configure_mappings()` once at startup.
- The thin repository runs against `uow.session` and returns aggregates directly.
- `InMemoryUnitOfWork` (dict-backed, explicit `track()`) ships alongside for tests.

```python
# sales/infrastructure/order_repository.py     - thin, intention-revealing
class SqlAlchemyOrderRepository:                  # implements OrderRepository (domain port)
    def __init__(self, uow: SqlAlchemyUnitOfWork) -> None:
        self._uow = uow

    def add(self, order: Order) -> None:
        self._uow.session.add(order)

    def get(self, order_id: OrderId) -> Order:
        order = self._uow.session.get(Order, order_id.value)
        if order is None:
            raise OrderNotFound(order_id)
        return order

    def find_open_for_customer(self, customer_id: CustomerId) -> list[Order]:
        return (
            self._uow.session.query(Order)
            .filter_by(customer_id=customer_id.value, status="OPEN")
            .all()
        )
```

```python
# sales/entrypoints/providers.py
def order_service() -> OrderService:
    uow = unit_of_work()                          # from bootstrap/ (mappings already configured)
    orders = SqlAlchemyOrderRepository(uow)
    return OrderService(uow=uow, orders=orders, bus=event_bus(), notifier=notifier())
```

### Other stores

The same `UnitOfWork` Protocol, the same repository ports, and the same `track()` /
`collect_new_events()` contract apply - only the implementation changes:

- **DynamoDB:** `DynamoUnitOfWork` buffers writes and flushes on `commit()` as a
  conditional `PutItem` / `TransactWriteItems`; repositories serialize aggregates to
  items explicitly.
- **Raw sqlite or another driver:** the repository hand-writes row-to-aggregate
  translation (a `<aggregate>_mapper.py` with pure `to_row` / `to_aggregate` functions
  when it grows).

The manual-translation form is also the escape hatch for SQL projects whose aggregates
are hostile to imperative mapping (deeply immutable structures, computed state).

### Test note

Domain unit tests run without the store's mapping or translation configuration so
aggregate classes stay uninstrumented (guarded by a fixture). See Section 11.4. Every
use-case write goes through a UoW; the service never commits repositories
individually. (ARCH-033)

## 7.3 Transactional outbox

- Mandatory when event publication or a transactional side-effect requires a delivery
  or consistency guarantee: integration events are written to an `outbox` table in the
  same transaction; a separate process publishes them. (ARCH-036)
- Optional (`publish-after-commit`) when no such guarantee is required.
- The machinery lives in `commons/infrastructure/outbox.py`.
