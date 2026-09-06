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

3. **Progressive Structure.** Structure grows when it hurts, not before. A context
   starts with flat modules (`domain/model.py`, `application/<capability>.py`,
   `infrastructure/<adapter>.py`). It is promoted to packages only past defined
   thresholds (Section 15). This standard defines the thresholds; it does not mandate
   the maximal structure from day one.

The standard is rule-based, deterministic, and verifiable so that it is consumable by
humans, by Claude Code, by an architecture-reviewer agent, and by CI.
