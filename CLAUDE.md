# Project Agent Instructions

These instructions govern how coding agents work in this repository. They are the whole
working rule set. Reading them is the reading requirement.

## What this system is

A single-candidate CV tailoring tool. One user, local only, not deployed, no auth, no
cloud. v2 starts with an empty database; v1 is a frozen archive in Git and is never
migrated, opened, or written to.

Almost everything the engine produces is regenerable in seconds: drafts, selections,
renders, projections. Getting one of them wrong costs a re-run. Calibrate effort to
that, not to the size of the codebase.

One thing is not regenerable, and it is where care belongs:

**Immutable records already written** — approved revisions, submitted artifacts, job
snapshots of postings that later vanish from the web. Overwriting one destroys evidence
that cannot be reproduced from anything else. This is forward-looking: it is about what
v2 accumulates, not about history.

## Specifications

`docs/v2/spec/` holds the approved v2 specifications. They are binding on what the
product does; they are not required reading before every task. `docs/v2/records/` holds
closed evidence, `docs/v2/process/` the multi-agent protocol, and `docs/v1/` the legacy
record. `docs/README.md` is the map.

Read the one that owns the subject you are changing:

| Changing | Read |
| --- | --- |
| Product scope, invariants, non-goals | `docs/v2/spec/product-spec.md` |
| Lifecycle, commands, queries, permissions | `docs/v2/spec/state-and-use-cases.md` |
| Layer boundaries, filesystem layout, schema shape | `docs/v2/spec/architecture.md` |
| Milestone stages and gates | `docs/v2/spec/implementation-plan.md` |
| What v1 did and why | `docs/v1/upgrade-handoff.md` |

If a specification conflicts with existing behavior, stop and say so. Do not
reinterpret a conflict silently. The pre-v1 generation workflow is retired; historical
sources and artifacts are evidence, not an active workflow.

Persistence exception, decided 2026-08-25: this file and
`docs/v2/spec/architecture.md` own the PostgreSQL/SQLAlchemy/Alembic baseline. Older
product and acceptance documents that still describe embedded database storage or list
PostgreSQL as a non-goal are superseded on that subject only; they do not trigger the
stop rule above.

## Change classes

The class follows from what the change touches, not from how it feels.

**Class A — local.** Does not touch `migrations/`, an artifact path, a public callable
signature, or a contracted message string. A message is contracted when a
specification, public interface, golden or snapshot, or deliberate test assertion makes
it one — not merely because some test happens to match on it.
Gates: the focused tests, then the non-browser suite once.

**Class B — contract.** Changes a stored value's meaning, a signature, a projection
field, or a contracted message.
Gates: Class A, plus golden hashes, the architecture test, and a deterministic no-AI CLI
run against the configured PostgreSQL service.
The reasoning goes in the commit message.

**Class C — schema or artifact paths.** A change to the baseline schema, or to where
immutable payloads live.
Gates: Class B, plus the browser suite and the Alembic migration-topology and empty-database
upgrade checks. A baseline revision change must be deliberate, with the generated schema
diff stated.

Gates are per boundary, not per commit, and the user runs them. While iterating, hand
over only the focused tests for what changed; hand over the class's full gate once, when
the work closes. Do not ask for the browser suite for changes that cannot affect a
rendering or browser path. A gate that already passed under the same conditions is not
fresh evidence — check the diff, the test count against its baseline, and which
interpreter produced the numbers. Predict the expected count and explain every
difference from it; an unexplained delta is a finding, not noise.

## What actually catches defects

These are cheap and have each caught a real bug in this repository. Prefer them over
process:

- **Run the deterministic CLI end to end** — `ingest → analyze → draft → validate → approve
  → render → ready → reconcile`, with `OPENAI_API_KEY` unset, against a fresh Workspace
  and a running configured PostgreSQL database.
  This is what found approval silently destroying unimported manual edits.
- **Golden hashes** — they must not move unless output was meant to change.
- **Immutability triggers** on records that must never be rewritten.
- **Derived guards.** Prefer deriving a check from the code or schema over maintaining a
  list by hand. Where a guard needs a list, make it a small list of deliberate
  exceptions, so forgetting to register something fails instead of passing. Inverting
  one such default to "immutable unless exempt" found a table that had been unguarded
  since M1.
- **Asking what a passing test actually proves.** A golden test was proving parity for a
  code path production no longer took.

Add regression coverage for a material bug only when existing coverage would not catch
it. Prefer extending or parameterizing the closest test over adding another item.

Never claim completion with "implemented" alone. Report what passed, what failed, and
what remains. A hard failure is never relabelled as a warning.

## Facts and AI boundaries

- Never invent, strengthen, merge, or "improve" candidate facts.
- One fact has one canonical location. Profiles may reference it; they may not create
  conflicting copies.
- New facts follow `pending -> confirmed -> canonical` unless explicitly confirmed by
  the user in the same message.
- Unsupported factual claims must block approval and `ready_qualified`, including in
  fast mode.
- AI proposes classification, selection, and wording. Canonical facts and deterministic
  validation remain authoritative.
- Preserve canonical historical job titles, dates, metrics, uncertainty, and source
  provenance.

## Immutable records

- Approved and submitted CV, HTML, PDF, job snapshot, and application records are
  immutable. Never overwrite or relocate one.
- Never invent a value a record never carried. A field that cannot be derived stays
  NULL.

## Scope

- Implement only approved v2.0 scope and respect the non-goals in
  `docs/v2/spec/product-spec.md`, except for its superseded persistence choice described
  above.
- The local FastAPI + React Web UI and its local PostgreSQL service are authorized in this
  worktree. Cloud deployment, authentication, multi-candidate support, and broad
  multi-provider support are not.
- Keep the CLI first-class. It calls the application layer directly, does not require
  FastAPI, and the deterministic workflow must reach Ready without an AI key.
- Do not begin Dashboard/tracking UI before the Web/API vertical slice reaches Ready
  with its central failure paths passing.
- Do not perform unrelated refactors or cleanup.
- Do not edit generated HTML by hand; fix the source, template, renderer, or rules.
- The dependency baseline is `docs/v2/spec/architecture.md` section 2. Add a dependency
  only when it enforces contracts, reduces rendering risk, or gives a concrete
  portability benefit within v2.0.

## Working rules

- Proceed by default. Stop only for a blocker, an unresolved specification conflict, a
  required semantic deviation, or material data-loss risk. Explain the issue and its
  consequences before asking for a decision.
- Internal implementation details may change freely when observable behavior, safety,
  and product semantics stay the same.
- Do not silently change workflow, validation behavior, fact semantics, application
  statuses, or artifact lifecycle.
- Work only in the v2 branch/worktree against an explicitly marked, isolated Workspace.
  Never write into the v1 archive. The `looks_legacy` guard refuses to open or mark a v1
  root; do not route around it.
- Preserve unrelated user changes in a dirty worktree. One agent at a time per worktree
  and isolated Workspace: concurrent edits race the test runner and make every
  measurement meaningless. Parallel agents are permitted only under
  `docs/v2/process/execution-protocol.md`, with separate git worktrees, disjoint file
  ownership, and isolated runtime and test resources.
- Small, intentional commits. Do not mix unrelated changes in one commit.
- Never use destructive Git or filesystem operations to simplify cleanup.
- Do not run tests. The user runs them. At the end of a boundary, hand over the ordered
  commands with what each one proves and what a pass looks like, and state plainly
  anything you could not verify because you did not run it.

## Documentation

`docs/v2/m4-remaining.md` is the active M4 state record. `docs/v2/m3-remaining.md` and
`docs/v2/m2-remaining.md` are their milestones' closed, frozen trackers. A record under
`docs/v2/records/` is frozen when its boundary closes: it keeps its own evidence and is
not updated with later state. Non-milestone cleanup items live in
`docs/v2/cleanup-todos.md`.

Decisions and their reasoning go in the commit message. Write a separate design brief
only for a Class C change whose reasoning will not fit there.

## Keeping this file small

Every control here was added because something went wrong once. Nothing removes them,
so without a counterweight this file can only grow, and the process drifts toward
treating every change as a release.

The counterweight: when closing a milestone, name one control that was retired, or
state that none was retirable and why. A guard that has never failed since it was added
is a candidate for merging into a derived check.

Retired 2026-08-19: the **Migration safety** section and the v1 arm of Class C. None of
those rules ever fired — they guarded a migration that was then not performed. Do not
re-add them; see `docs/v2/m2-remaining.md`.

PostgreSQL replacement 2026-08-25: retired the built-in Workspace backup/restore control
and the frozen file-database schema-fingerprint control. This task starts every development
database empty; Alembic's single-head/revision registration guard and explicit foreign-key
integrity check now own schema safety. `looks_legacy` remains the archive-isolation guard.

M3 close 2026-08-23: **no control was retirable.** Every remaining control still guards
an active failure mode, and M3 exercised several of them: fresh count reconciliation
caught a stale baseline, the offline CLI exposed immutable-record omissions, and review
found defects green tests did not. The two deliberately-empty exception sets were not
considered candidates, as required.
