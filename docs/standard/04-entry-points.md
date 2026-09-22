# 4. Entry Points

## 4.1 Flow

```text
External stimulus -> Entrypoint -> Application use case -> Domain
```

## 4.2 Structure: grouped by transport kind, one file per aggregate

`<context>/entrypoints/` groups by transport kind, not by a single flat file per
kind:

```text
<context>/entrypoints/
├── web/            # HTTP/GraphQL routes and other request/response APIs
│   ├── order.py    #   one file per aggregate module
│   └── customer.py
├── events/         # message/event consumers (Kafka/RabbitMQ/SQS/...)
│   └── order_placed.py    #   named for what it does; not forced into an
│                           #   aggregate-name pattern the way web/ is
├── crons/          # scheduled jobs
│   └── expire_stale_orders.py
└── cli.py          # CLI stays a flat file; add a cli/ folder the same way
                     #   if it ever needs to split
```

There is no `providers.py`. Each entrypoint file defines its own tiny
getter for the one service it needs (a `configure()`/`get_x_service()` pair,
or the transport's own DI hook), set once at startup by the composition root
(`main.py`) -- the only module allowed to import `bootstrap/` (ARCH-017).
This keeps each aggregate module's wiring self-contained: extracting
`quote/` into its own service later needs no untangling of a
context-wide wiring file shared with other aggregate modules.

`web/` gets one file per aggregate module because a REST-style resource maps
cleanly onto one aggregate. `events/` and `crons/` do not: an event consumer or a
scheduled job is better named for the specific thing it does
(`order_placed.py`, `expire_stale_orders.py`) than forced into
`<aggregate_name>.py`. What both share is the real rule underneath the naming:
**a file serves at most one aggregate module** - split it, don't let one handler
reach into two aggregates' application services (ARCH-056). `entrypoints/`
groups by transport kind first because everything under one kind shares
concerns (a router, a consumer group, a scheduler) that a per-aggregate split
alone does not.

## 4.3 Rules

- Entrypoints are inbound adapters: HTTP, GraphQL, Kafka/RabbitMQ/SQS consumers, CLI,
  cron.
- An entrypoint translates a stimulus into a command/query, calls one application
  service method, and maps the result or exception back to the transport (status codes,
  serialization). (ARCH-004 family)
- An entrypoint obtains a fully wired service through its own getter, configured once
  at startup by `main.py` (the composition root). It MUST NOT construct outbound
  adapters itself, and MUST NOT import `bootstrap/` itself. (ARCH-009, ARCH-017)
- An entrypoint MUST NOT call persistence, adapters, or the database directly
  (`repo.save(...)`, `session.execute(...)`, `http_client.get(...)`). The only thing it
  calls is the application service. (ARCH-009)
- An entrypoint MUST NOT contain business logic. (ARCH-010, SHOULD)
- An entrypoint MUST NOT call another entrypoint. (ARCH-011)
- An entrypoint file serves at most one aggregate module. (ARCH-056, SHOULD)
- An entrypoint MAY import `domain/model/exceptions.py` (and the `commons` base errors)
  solely to map domain exceptions to transport responses.
- Pydantic request/response models live only in entrypoints.

## 4.4 Exceptions to the rule

- Health and readiness endpoints MAY read backing-service state directly; they are not
  business use cases.
- A pure pass-through admin or debug endpoint MAY be exempt if it is explicitly marked
  and excluded from the public surface. This is discouraged and requires justification.

## 4.5 HTTP response shaping is centralized, not per-handler

When a web entrypoint context wants a uniform response shape -- a success/error
envelope, standard error formatting, a consistent status-code mapping -- that shaping
is applied by **one mechanism the composition root registers once** (e.g. ASGI
middleware added in `main.py`), never rebuilt inside each handler. (ARCH-057, SHOULD)

```text
bootstrap/envelope.py    # e.g. an ASGI middleware wrapping every JSON response
main.py                  # app.add_middleware(EnvelopeMiddleware) -- registered once
<context>/entrypoints/web/order.py   # handlers return their plain response model;
                                      #   they never build the envelope themselves
```

The envelope's exact shape (field names, whether errors are a list or a single
message, which status codes map where) is a project decision this rule does not
mandate. What it does mandate is *where* that decision lives: one place, applied
uniformly, not duplicated -- and inevitably drifting -- across every handler.
