# 4. Entry Points

## 4.1 Flow

```text
External stimulus -> Entrypoint -> Application use case -> Domain
```

## 4.2 Rules

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
- An entrypoint MAY import `domain/model/exceptions.py` (and the `commons` base errors)
  solely to map domain exceptions to transport responses.
- Pydantic request/response models live only in entrypoints.

## 4.3 Exceptions to the rule

- Health and readiness endpoints MAY read backing-service state directly; they are not
  business use cases.
- A pure pass-through admin or debug endpoint MAY be exempt if it is explicitly marked
  and excluded from the public surface. This is discouraged and requires justification.
