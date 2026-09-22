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
├── cli.py          # CLI stays a flat file; add a cli/ folder the same way
│                    #   if it ever needs to split
└── providers.py     # one file, wires every aggregate module's service for
                      #   this context (unchanged - ARCH-037)
```

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
- An entrypoint obtains a fully wired service from
  `<context>/entrypoints/providers.py` (which pulls from the `bootstrap/` container).
  It MUST NOT construct outbound adapters itself. (ARCH-009)
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
