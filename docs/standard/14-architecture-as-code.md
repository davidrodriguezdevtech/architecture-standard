# 14. Architecture as Code

## 14.1 Tooling map (Python)

| Mechanism | Tool | Rules | Runs in |
|---|---|---|---|
| Import contracts (layering, independence, cycles) | import-linter (`.importlinter`) | 001-003, 005, 006, 008, 011-015, 017, 034, 035 | CI + pre-commit |
| Import-graph queries / bespoke asserts | grimp | 007, cycle detection, "who imports X" | pytest arch suite |
| Banned symbols/patterns per layer | ruff (`flake8-tidy-imports` banned-api, `TID`, `TCH`) | 003, 004, 028 | CI + pre-commit |
| AST structural rules | custom `ast` checker shipped with the standard | 023, 031, 018, 019, 030 (service size: methods/lines/params), 040, 041 (promotion thresholds), 043 (envelope shape) | CI + pytest |
| ADR waiver expiry | validator date check over `docs/adr/` | 021*, 036, any waived MUST | CI |
| Package boundaries with a public API | tach (`tach.toml`) | 012, 042, 045 | CI |
| Event schema / contract testing | pydantic/jsonschema export + consumer fixtures; optionally Pact | 024, 043, 044 | CI (producer & consumer) |
| Test taxonomy | pytest markers + a conftest rule forbidding infra imports in domain tests | 038 | CI |
| Coverage gates per layer | coverage.py with per-path thresholds | Section 11.5 | CI |
| Manual review checklist | shipped PR checklist for the "manual" rules | 016, 021*, 027, 029, 036, 039, 042 | code review |

## 14.2 Confidence tiers

- **full** (~20 rules): deterministic pass/fail on the exact rule.
- **partial** (~14 rules): catches common violations; edge cases need review.
- **manual** (~6 rules): only a human or an LLM reviewer can judge.

## 14.3 The validator

A single entrypoint `python -m arch_standard.check` runs import-linter plus the AST
checker plus schema validation and prints:

```text
ARCH-001  PASS
ARCH-012  FAIL  sales/application/order_placement.py:4  imports billing.domain.invoice
ARCH-023  FAIL  sales/domain/model/events.py:12         OrderCreate is not past-tense / not frozen
```

It exits non-zero on any MUST failure and warns on SHOULD.
