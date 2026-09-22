# Contributing to and consuming this repository

This file is about **process**, not architecture: how `arch-standard` and
`arch-commons` get versioned, built, and pinned by projects that depend on
them — especially when more than one session or developer is working against
this repo and a consuming project at the same time. The rule catalog itself
(`rules/*.yaml`, generated into `ARCHITECTURE_STANDARD.md`) governs what a
*consuming project's own code* must look like; this file governs how you get
a working copy of the standard into that project in the first place.

## The one rule

**A numbered wheel (`0.3.0`, `0.4.0`, …) is only ever built from `master`, in
the same commit or merge that bumps the version.** Never from a feature
branch tip, never amended into an already-built version after the fact.

That is the whole rule. Everything below is why it exists and what to do
instead when `master` doesn't yet have what you need.

## Why this is the rule

Neither package is published to a real registry today — projects consume
them from a local `dist/` folder via `find-links`, or via a direct git
reference. Nothing about `uv build` or `uv add` stops you from building a
wheel off whatever branch you happen to have checked out and labelling it
with whatever the version file currently says. That is exactly how a version
number stops meaning one thing: two sessions each build "0.3.0" from two
different, still-diverging branch tips, and now "pin 0.3.0" is ambiguous
depending on whose wheel you happened to install.

This is not a hypothetical. In one afternoon:

- A rule-catalog fix was committed, then **amended in place** rather than
  given a new version, because "nobody had consumed it yet" — except a
  downstream session had already pinned an intermediate build of the same
  number. Two consumers, two different meanings for `0.3.0`.
- A packaging change to `arch-commons` (dropping `commons/adapters/__init__.py`
  to make it a namespace portion) landed in a shared, uncommitted working
  tree. A sibling package's version number got copied onto it by whoever
  next edited the pin file, without arch-commons' own content change ever
  getting its own deliberate bump or changelog entry.
- A file move got attributed to the wrong session entirely, because a
  shared git index carries no authorship — "who staged this" is not
  answerable from the index alone.

None of this was carelessness. Every session involved was being reasonably
careful. The workflow itself had no way to prevent it: an unreleased branch
tip was being treated as if it were a stable, citable version.

## What to do instead

**If `master` already has what you need:** pin the real version number, from
a wheel built from `master`. This is the common case and needs no ceremony.

**If you need content that is only on a branch, not yet merged to `master`:**
pin a direct git reference to that branch or commit instead of a version
number — do not build a same-numbered wheel into the shared `dist/` folder to
work around it. This is already a supported dependency form (see the
`# where arch-standard and arch-commons are direct git references above`
comment in the generated `pyproject.toml.jinja` template):

```toml
dependencies = [
    "arch-standard @ git+file:///C:/Users/you/dev/architecture-standard@feat/some-branch",
]
```

A git reference makes the ambiguity structurally impossible instead of
relying on someone remembering to ask first: what you are running is always
legible from the dependency spec itself. A plain version number means
"released, from `master`." A git reference means "this specific branch, not
yet real — expect it to move."

When that branch merges and the version genuinely bumps, switch the pin back
to the numbered release.

**If you are the one merging a branch that changes rule-catalog content, or
either package's actual code:** the version bump is part of that same merge,
not a follow-up commit, and not something borrowed from a sibling package.
`arch-standard` and `arch-commons` are versioned independently — bumping one
because you bumped the other, without an actual content change to justify it,
recreates the exact ambiguity this file exists to prevent. If you are
bumping both in the same merge because you are deliberately releasing them
together, say so in the changelog entry; don't let the matching numbers be
the only evidence of that decision.

## Why not a pre-release/dev suffix instead?

The standard Python convention for "this is a build off unreleased code" is a
PEP 440 local or dev suffix (`0.4.1.dev0+g<sha>`). That doesn't work here:
`arch_standard.version_stamp.parse_semver` requires a strict
`MAJOR.MINOR.PATCH` string and raises on anything else, so a dev-suffixed
version would fail `arch-standard check` and `release-check` outright. The
git-reference approach above sidesteps that entirely rather than fighting the
parser — it doesn't touch the version string at all.

## Quick checklist before you build or consume a wheel

- [ ] Is the content I need already on `master`? If yes, pin the number,
      build from `master`, done.
- [ ] If not, am I about to build a wheel from a branch tip anyway? Don't —
      use a git-ref pin instead.
- [ ] Am I bumping a version because *this* package's content changed, or
      because a sibling package's version changed? Only the former is a
      reason to bump.
- [ ] Does the changelog entry actually describe what changed, or does the
      version number merely match a sibling's?
- [ ] If I already built and shared a wheel under a given number, and the
      content needs to change again — that's a **new** version, never an
      amend of the one already shared.
