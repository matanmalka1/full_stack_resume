# Project Agent Instructions

These instructions govern how coding agents work in this repository. They are the whole
working rule set. Reading them is the reading requirement.

## What this system is

A single-candidate CV tailoring tool. One user, local only, not deployed, no auth, no
cloud. The live v1 data is 25 applications and 192 artifact versions.

Almost everything the engine produces is regenerable in seconds: drafts, selections,
renders, projections. Getting one of them wrong costs a re-run. Calibrate effort to
that, not to the size of the codebase.

Two things are not regenerable, and they are where care belongs:

1. **The v1 historical record** — 25 applications, 192 artifacts, job snapshots of
   postings that no longer exist, CVs that were actually sent. One-shot migration.
2. **Immutable records already written** — approved revisions, submitted artifacts,
   snapshots. Overwriting one destroys evidence.

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
| Migration of v1 data | `docs/v2/spec/migration-plan.md` |
| Milestone stages and gates | `docs/v2/spec/implementation-plan.md` |
| What v1 did and why | `docs/v1/upgrade-handoff.md` |

If a specification conflicts with existing behavior, stop and say so. Do not
reinterpret a conflict silently. The pre-v1 generation workflow is retired; historical
sources and artifacts are evidence, not an active workflow.

## Change classes

The class follows from what the change touches, not from how it feels.

**Class A — local.** Does not touch `migrations/`, an artifact path, a public callable
signature, or an error message a test matches on.
Gates: the focused tests, then the non-browser suite once.

**Class B — contract.** Changes a stored value's meaning, a signature, a projection
field, or a matched message.
Gates: Class A, plus golden hashes, the architecture test, and an offline CLI run.
The reasoning goes in the commit message.

**Class C — schema, artifact paths, or v1 data.** A new migration, a change to where
immutable payloads live, or anything touching the v1 historical record.
Gates: Class B, plus the browser suite, a `0001`-only database upgrading cleanly to
head, and — for v1 data — the migration-safety rules below.

Gates are per boundary, not per commit. While iterating, run only the focused tests for
what changed; run the class's full gate once, when the work closes. Do not run the browser
suite for changes that cannot affect a rendering or browser path. Re-running a gate that
already passed under the same conditions is not evidence — check the diff, the test count
against its baseline, and which interpreter produced the numbers.

## What actually catches defects

These are cheap and have each caught a real bug in this repository. Prefer them over
process:

- **Run the CLI offline, end to end** — `ingest → analyze → draft → validate → approve
  → render → ready → reconcile`, with `OPENAI_API_KEY` unset, against a fresh Workspace.
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

## Migration safety

These apply to the v1 historical record and to immutable records already written. They
are the one place where full ceremony is warranted.

- Historical and submitted CV, HTML, PDF, job snapshot, and application artifacts are
  immutable. Never overwrite or relocate them.
- Do not migrate live data until a complete snapshot exists and is verified, restore
  instructions exist, migration tests pass, and every historical record and artifact is
  accounted for.
- Test migration against a copy or snapshot before live migration.
- If any migration safety check fails, stop. Do not partially continue or guess.
- Never invent an identity for a historical record that was never recorded. A field that
  cannot be derived stays NULL.
- Preserve historical data and output meaning, not the legacy architecture.

## Scope

- Implement only approved v2.0 scope and respect every non-goal in
  `docs/v2/spec/product-spec.md`.
- The local FastAPI + React Web UI is authorized in this worktree. Cloud deployment,
  authentication, PostgreSQL, multi-candidate support, and broad multi-provider support
  are not.
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
  required semantic deviation, material data-loss risk, or a migration-safety failure.
  Explain the issue and its consequences before asking for a decision.
- Internal implementation details may change freely when observable behavior, safety,
  and product semantics stay the same.
- Do not silently change workflow, validation behavior, fact semantics, application
  statuses, migration behavior, or artifact lifecycle.
- Work only in the v2 branch/worktree against an explicitly marked, isolated Workspace.
  Never point any command at live v1 data.
- Preserve unrelated user changes in a dirty worktree. One agent at a time: concurrent
  edits race the test runner and make every measurement meaningless.
- Small, intentional commits. Do not mix unrelated changes in one commit.
- Never use destructive Git or filesystem operations to simplify migration or cleanup.

## Documentation

`docs/v2/m2-remaining.md` is the single record of state — what is done, what remains,
what is blocked. Nothing else records state. A record under `docs/v2/records/` is frozen
when its boundary closes: it keeps its own evidence and is not updated with later state.
Non-milestone cleanup items live in `docs/v2/cleanup-todos.md`.

Decisions and their reasoning go in the commit message. Write a separate design brief
only for a Class C change whose reasoning will not fit there.

## Keeping this file small

Every control here was added because something went wrong once. Nothing removes them,
so without a counterweight this file can only grow, and the process drifts toward
treating every change as a release.

The counterweight: when closing a milestone, name one control that was retired, or
state that none was retirable and why. A guard that has never failed since it was added
is a candidate for merging into a derived check.
