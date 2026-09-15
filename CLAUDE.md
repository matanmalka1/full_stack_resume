# Project Agent Instructions

How coding agents work in this repository. This is the whole rule set.

## What this system is

A single-candidate CV tailoring tool. One user, no auth, one candidate. The database
starts empty. `base/` and `profiles/` hold the live source facts.

Almost everything the engine produces is regenerable in seconds — drafts, selections,
renders, projections. Getting one wrong costs a re-run. Calibrate effort to that.

One thing is not regenerable, and that is where care belongs:

**Immutable records already written** — approved and submitted CV, HTML, PDF, job
snapshot, and past application history. A job snapshot preserves a posting that later
vanishes from the web. Never overwrite or relocate one; overwriting destroys evidence
nothing else can reproduce. Never invent a value a record never carried — a field that
cannot be derived stays NULL. This does not freeze an application's current status: a
status field may transition per the lifecycle rules in `docs/spec/state-and-use-cases.md`.
What is immutable is the history and artifacts already written, not the live state that
lifecycle transitions are defined to change.

## Specifications

`docs/spec/` holds the binding specifications. They are not required reading before every
task. Read the one that owns what you are changing:

| Changing | Read |
| --- | --- |
| Product scope, invariants, non-goals | `docs/spec/product-spec.md` |
| Lifecycle, commands, queries, permissions | `docs/spec/state-and-use-cases.md` |
| Layer boundaries, filesystem layout, schema shape | `docs/spec/architecture.md` |
| Test layers and release gates | `docs/spec/test-and-acceptance-plan.md` |

If a specification conflicts with existing behavior, say so. Do not reinterpret a
conflict silently.

## Gates

The user runs every gate. You never run tests — you hand over the commands.

Every change needs the focused tests for what it touched. A **boundary** is a delivery
point — the work handed back to the user as done, whether that's a task, a PR, or an
explicit checkpoint the user names. It is not any internal step inside that work.
Choose gates from the actual diff and affected behavior:

- Frontend-only changes need frontend checks only.
- Backend-only changes need backend checks only.
- Changes affecting both need checks for both, including shared contracts where touched.
- Prefer focused tests for the affected behavior. A boundary does not automatically
  require a full frontend, backend, or combined suite. Broaden only for a concrete
  uncovered risk, a failure, or an explicit CI/release requirement; state why.
- Documentation-only changes need consistency review, not product test suites.

Three kinds of change need additional focused evidence:

- **A schema change** (`alembic/`) also needs the migration-topology and empty-database
  upgrade checks, with the generated schema diff stated.
- **A change to rendering or an artifact path** also needs the golden hashes and the
  relevant browser tests.
- **A change to a stored value's meaning, a public application/API signature, or a projection field**
  also needs the pipeline test against a fresh PostgreSQL database
  (`tests/test_pipeline_end_to_end.py`) — `ingest → analyze → draft → validate → approve
  → render → ready → reconcile`, `OPENAI_API_KEY` unset. It drives the application
  services directly, so it proves the engine works rather than that one client knows how
  to call it. Analysis is the one step that needs a provider (see Facts and AI
  boundaries); the rest of the chain runs with none, and that is what this test holds:
  everything downstream of an existing analysis reaches Ready without AI.

While iterating, hand over only the focused commands. Hand over the boundary's scoped gates
once, when the work closes, ordered, with what each command proves. A gate that already
passed under the same conditions is not fresh evidence — check the diff and the test count
against its baseline before asking for a re-run.

Golden hashes must not move unless output was meant to change. Records that must never
be rewritten are protected by immutability triggers, not by convention.

**Derived guards.** Derive a check from the code or schema rather than maintaining a list
by hand. Where a guard needs a list, make it a list of deliberate exceptions, so
forgetting to register something fails instead of passing.

Add regression coverage for a material bug only when existing coverage would miss it.
Extend the closest test rather than adding another.

Report what passed, what failed, and what remains. Never claim completion with
"implemented" alone. A hard failure is never relabelled as a warning.

## Facts and AI boundaries

- Never invent, strengthen, merge, or "improve" candidate facts — the fact and its
  meaning must not change. Rewording and combining sentences to fit a role is allowed
  when the fact and its meaning are unchanged and the validation contract accepts it;
  the restriction is on the fact, not on prose.
- One fact has one canonical location. Profiles may reference it; they may not create
  conflicting copies.
- New facts follow `pending -> confirmed -> canonical` unless the user confirms in the
  same message.
- Unsupported factual claims block approval and `ready_qualified`. No chained or
  no-pause flow may bypass that; a blocker refuses whatever is driving it.
- AI proposes classification, selection, wording, and — per `docs/spec/product-spec.md`
  §2 "Semantic analysis authority" — requirement extraction, interpretation, and which
  canonical facts answer a requirement. Creating a new analysis needs a provider; there
  is no rules-based fallback for it, silent or otherwise. Canonical facts and
  deterministic validation stay authoritative — authoritative over meaning, not over
  exact wording. Deterministic validation may enforce semantic equivalence to the
  canonical fact; it is not required to demand verbatim copying, and a check that does
  so is enforcing more than this rule requires.
- Deterministic policy keeps every check it can run itself: source attestation against
  the signed snapshot, canonical-fact eligibility, requirement identity, structural
  completeness, numeric and compositional consistency, boundary-fact applicability, Fit
  calculation, review routing, and every approval boundary. A proposal may be narrowed
  by those checks; it may never be widened by them. The closed concept vocabulary in
  `config/requirements.json` no longer decides coverage — it states boundary
  applicability and scale ordering, both of which only lower a verdict.
- Preserve canonical job titles, dates, metrics, uncertainty, and source provenance.

## Working rules

- Stop for a blocker, an unresolved specification conflict, an *unapproved* semantic
  deviation, or material data-loss risk. Explain the issue and its consequences first.
  Implementing a deviation the spec or the user has already approved is not a stop
  condition — that is just the task.
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
  which the API calls directly. Once an analysis exists, the deterministic workflow
  reaches Ready with no AI key.
- Do not edit generated HTML by hand; fix the source, template, renderer, or rules.
- Add a dependency only when it enforces a contract, reduces rendering risk, or gives a
  concrete portability benefit. The baseline is `docs/spec/architecture.md` section 2.
- One agent at a time per worktree.
