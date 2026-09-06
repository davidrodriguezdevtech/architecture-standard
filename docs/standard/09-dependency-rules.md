# 9. Dependency Rules

Every rule carries the full schema: ID, name, description, rationale, correct example,
incorrect example, level (MUST/SHOULD/MAY), automation (full/partial/manual), and tier
(core/full). The machine-readable source of truth is `rules/*.yaml`; the tables below
are generated from it.

Each rule is tagged `tier: core` or `tier: full`. Core rules are binding from day one
and machine-checkable; `arch-standard check --core` runs exactly that set, and the
table below lists it before the full catalog.

<!-- RULES_CATALOG -->
