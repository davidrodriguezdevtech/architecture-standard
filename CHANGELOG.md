# Changelog

All notable changes to the Architecture Standard's rule catalog are recorded here,
one version per section. The compatibility policy (spec Section 16.3) governs
what kind of change requires which version bump; `arch-standard release-check`
enforces it, `arch-standard changelog` renders these entries.

## 0.1.0

Initial catalog and tooling: the rule catalog (`rules/*.yaml`), the `arch_standard`
validator package (import-linter contracts, the AST checker, structure and context-graph
checks), `ARCHITECTURE_STANDARD.md` generation, and CI. Includes the aggregate-module
level, the `<context>/read/` layer, the declared context dependency graph, and rule tiers
(12 core rules).
