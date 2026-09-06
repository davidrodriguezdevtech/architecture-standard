# Architecture Decision Records

A rule waiver is an ADR with this frontmatter:

```
---
waives: ARCH-021        # the rule id being waived
scope: <one line>       # exactly what is exempted
expires: 2026-12-05     # ISO date; default 90 days from creation
---
```

The validator's allowlist is built from non-expired waivers only. A lapsed
waiver re-activates the rule and fails the next build.
