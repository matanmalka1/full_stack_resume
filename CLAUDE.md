# Project Agent Instructions

How coding agents work in this repository. This is the whole rule set.

## What this system is

A single-candidate CV tailoring tool. One user, no auth, one candidate. The database
starts empty. `base/` and `profiles/` hold the live source facts.

Persistence is PostgreSQL via SQLAlchemy, with Alembic migrations. Immutable payloads sit
behind an object-storage abstraction: local by default, optionally an S3-compatible
bucket. The deterministic workflow reaches Ready with nothing configured, no cloud SDK,
and no AI key.

Almost everything the engine produces is regenerable in seconds — drafts, selections,
renders, projections. Getting one wrong costs a re-run. Calibrate effort to that.

One thing is not regenerable, and that is where care belongs:

**Immutable records already written** — approved revisions, submitted artifacts, job
snapshots of postings that later vanish from the web. Overwriting one destroys evidence
nothing else can reproduce.

## Specifications

`docs/spec/` holds the binding specifications. They are not required reading before every
task. Read the one that owns what you are changing:

| Changing | Read |
| --- | --- |
| Product scope, invariants, non-goals | `docs/spec/product-spec.md` |
| Lifecycle, commands, queries, permissions | `docs/spec/state-and-use-cases.md` |
| Layer boundaries, filesystem layout, schema shape | `docs/spec/architecture.md` |

If a specification conflicts with existing behavior, say so. Do not reinterpret a
conflict silently.

## Gates

The user runs every gate. You never run tests — you hand over the commands.

Every change needs the focused tests for what it touched. At the end of a boundary, the
non-browser suite once.

Three things earn more than that, and only these:

- **A schema change** (`alembic/`) also needs the migration-topology and empty-database
  upgrade checks, with the generated schema diff stated.
- **A change to rendering or an artifact path** also needs the golden hashes and the
  browser suite.
- **A change to a stored value's meaning, a public signature, or a projection field**
  also needs the deterministic no-AI pipeline test against a fresh PostgreSQL database
  (`tests/test_pipeline_end_to_end.py`).

While iterating, hand over only the focused commands. Hand over the boundary's full gate
once, when the work closes, ordered, with what each command proves. A gate that already
passed under the same conditions is not fresh evidence — check the diff and the test count
against its baseline before asking for a re-run.

## What actually catches defects

Cheap, and each has caught a real bug here. Prefer these over process:

- **Run the deterministic pipeline end to end** — `ingest → analyze → draft → validate
  → approve → render → ready → reconcile`, `OPENAI_API_KEY` unset, fresh database. It
  drives the application services directly, so it proves the engine works rather than
  that one client knows how to call it. This found approval silently destroying
  unimported manual edits.
- **Golden hashes** — they must not move unless output was meant to change.
- **Immutability triggers** on records that must never be rewritten.
- **Derived guards.** Derive a check from the code or schema rather than maintaining a
  list by hand. Where a guard needs a list, make it a list of deliberate exceptions, so
  forgetting to register something fails instead of passing.
- **Asking what a passing test actually proves.** A golden test was proving parity for a
  code path production no longer took.

Add regression coverage for a material bug only when existing coverage would miss it.
Extend the closest test rather than adding another.

Report what passed, what failed, and what remains. Never claim completion with
"implemented" alone. A hard failure is never relabelled as a warning.

## Facts and AI boundaries

- Never invent, strengthen, merge, or "improve" candidate facts.
- One fact has one canonical location. Profiles may reference it; they may not create
  conflicting copies.
- New facts follow `pending -> confirmed -> canonical` unless the user confirms in the
  same message.
- Unsupported factual claims block approval and `ready_qualified`. No chained or
  no-pause flow may bypass that; a blocker refuses whatever is driving it.
- AI proposes classification, selection, and wording. Canonical facts and deterministic
  validation stay authoritative.
- Preserve canonical job titles, dates, metrics, uncertainty, and source provenance.

## Immutable records

- Approved and submitted CV, HTML, PDF, job snapshot, and application records are
  immutable. Never overwrite or relocate one.
- Never invent a value a record never carried. A field that cannot be derived stays NULL.

## Working rules

- Proceed by default. Stop only for a blocker, an unresolved specification conflict, a
  required semantic deviation, or material data-loss risk. Explain the issue and its
  consequences before asking.
- Internal implementation details may change freely when observable behavior, safety, and
  product semantics stay the same.
- Do not silently change workflow, validation behavior, fact semantics, application
  statuses, or artifact lifecycle.
- React is the product interface and FastAPI is the only user-facing adapter; React
  reaches the system through it and nowhere else. The worker calls the same application
  layer as an internal execution host, not as a second client. A second user-facing
  surface for a use-case the API already owns is not added.
- The system runs as two processes sharing one PostgreSQL database, neither
  supervising the other: `uvicorn cv_engine.runtime.asgi:app` serves HTTP and creates
  Operations; `python -m cv_engine.worker` executes them through the Operation runner.
  The API starts no background work.
- The project root is fixed at the installed code location. It is not selectable by
  argument, setting, or environment variable. A test needing another root injects
  `AppPaths.from_root(...)` into composition.
- Routers map HTTP to a use-case and back. Logic belongs to the application layer,
  which the API calls directly. The deterministic workflow reaches Ready with no AI key.
- Do not edit generated HTML by hand; fix the source, template, renderer, or rules.
- Add a dependency only when it enforces a contract, reduces rendering risk, or gives a
  concrete portability benefit. The baseline is `docs/spec/architecture.md` section 2.
- Preserve unrelated user changes in a dirty worktree. One agent at a time per worktree.
- Small, intentional commits. Decisions and their reasoning go in the commit message.
- Never use destructive Git or filesystem operations to simplify cleanup.

## Keeping this file small

Every rule here was added because something went wrong once. Nothing removes them, so
without a counterweight this file only grows and the process drifts toward treating every
change as a release.

The counterweight: when closing a milestone, name one control that was retired, or state
that none was retirable and why. A guard that has never fired since it was added is a
candidate for merging into a derived check.
