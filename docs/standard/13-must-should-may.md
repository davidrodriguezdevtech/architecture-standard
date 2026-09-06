# 13. MUST / SHOULD / MAY

| Level | Meaning | On deviation |
|---|---|---|
| MUST | architectural invariant | build fails, no merge. Exception = documented ADR + standard maintainer approval |
| SHOULD | strong default | allowed with a one-line justification in the PR or an ADR; reviewer must acknowledge |
| MAY | genuine project choice | documented so it reads as sanctioned, not accidental |

`MUST*` is a conditional MUST: it applies when the stated condition holds (for example
ARCH-021 and ARCH-036).

## Exception process

A `docs/adr/NNNN-*.md` file records the rule waived, the reason, the scope, and a
mandatory `expires:` date (default 90 days). The validator generates its allowlist from
non-expired ADRs only - a lapsed waiver silently re-activates the rule and fails the
next build, forcing a conscious renew-or-fix. CI prints the count of active waivers per
rule on every PR.
