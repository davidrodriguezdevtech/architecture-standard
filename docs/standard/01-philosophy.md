# 1. Philosophy

Organize code by business first, then apply Clean/Hexagonal inside each business
capability. The top architectural level represents business boundaries (bounded
contexts), never technology (`controllers/`, `services/`, `repositories/`).

Three load-bearing ideas:

1. **The Dependency Rule.** Source-code dependencies point inward:
   `entrypoints -> application -> domain`, and `infrastructure -> domain/application`.
   The domain depends on nothing. Infrastructure is plugged in, never imported by the
   core.

2. **Business-capability cohesion at the top.** A change to "how orders work" touches
   one context. A change to "how we talk to Postgres" touches one adapter module.

3. **Fixed shape, growing content.** The folder structure is canonical and identical
   in every project built on this standard; what grows is the set of files inside it.
   A file does not exist until it has content, but its location is decided in
   advance. There is no "start flat, restructure later" step and therefore no
   judgement call about when to restructure - which is the point: the standard exists
   to make "where does this go?" answerable without judgement. The thresholds in
   Section 15 flag model problems, not layout problems.

The standard is rule-based, deterministic, and verifiable so that it is consumable by
humans, by Claude Code, by an architecture-reviewer agent, and by CI.
