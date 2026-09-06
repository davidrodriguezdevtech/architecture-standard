# 16. Reuse

The canonical repository is laid out as a pipeline: a machine-readable rule catalog is
the source of truth, and every other artifact is generated from or driven by it.

```text
architecture-standard/   (canonical)
├── ARCHITECTURE_STANDARD.md          # human spec (English), generated from rules/ + prose
├── rules/*.yaml                      # machine-readable catalog - source of truth
├── checks/                           # the validator: import-linter template + AST checker + schema tools
├── templates/                        # project skeleton (copier)
├── skills/architecture/SKILL.md      # the Superpowers skill
└── reviewers/architecture-reviewer/  # subagent definition
```

## Consumption paths

1. **Human** - reads `ARCHITECTURE_STANDARD.md`.
2. **New project** - `copier copy` produces the `src/` skeleton plus `.importlinter`,
   CI, and the `check` command.
3. **Superpowers skill** - triggers on "new bounded context", "add a use case", "where
   does X go", "review architecture". Loads the relevant rule subset plus the decision
   trees. Points Claude Code at `rules/*.yaml`.
4. **architecture-reviewer subagent** - given a diff, loads `rules/`, runs `checks/`,
   judges the "manual" rules with an LLM, and posts an `ARCH-xxx PASS/FAIL` report as
   PR comments.
5. **CI** - runs `checks/` on every PR; MUST failures block.

## Authoring constraints for agent-consumability

- Every rule has a stable ID, a single level, an `automation` field, a one-paragraph
  rationale, and one correct plus one incorrect example.
- The rule catalog is YAML (source of truth); Markdown is generated.
- Decision guidance is given as decision trees and checklists, not prose.
- Structure is given as a literal tree plus a "what goes where" table.
- Every rule is self-contained - no "as discussed above".
