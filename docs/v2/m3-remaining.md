# M3 — remaining work

Status tracker. Updated as boundaries close. Authority for scope remains
`docs/v2/spec/implementation-plan.md` §5.1–§5.4; this file only tracks state.

Supersedes `docs/v2/m2-remaining.md`, which is M2's closed tracker and is not updated
with later state.

## Where things are written

One fact, one place. This file is the only record of *state*.

| Question | Answer lives in |
| --- | --- |
| What is done, what remains, what is blocked | **this file** |
| What was decided and why | the commit message, or that boundary's design brief |
| Proof that something ran | the boundary's close-out section, the commit, the test run |
| Stages and gates per milestone | `docs/v2/spec/implementation-plan.md`, stable |
| Non-milestone cleanup items | `docs/v2/cleanup-todos.md` |
| M2's state, frozen | `docs/v2/m2-remaining.md` |

Evidence is not copied here. A closed item names its commit and, where one exists, its
close-out record; the numbers live there.

## What M3 is

Prove the complete workflow through the Application API before building a large frontend.
The HTTP layer is the smaller half of the work. The larger half is that several
application commands the slice requires do not exist yet: the action policy in
`application/state.py` names them as available actions and nothing implements them.

Three decisions were taken before the stages were written, and they are settled:

1. **Deterministic slice first, AI last.** Stages A–F reach Ready with `OPENAI_API_KEY`
   unset. Stage G adds the §5.3 AI tasks.
2. **TypeScript generation ships in M3**, via `openapi-typescript` only. No React, Vite,
   or Tailwind — those are M4.
3. **`fastapi` plus `httpx` (test extra) only.** Tests drive the real app through
   Starlette's `TestClient`. `uvicorn` and `cv web` are M6 §8.1.

Two further contracts, settled during review:

- `api -> application`. `api` never imports `runtime` or `infrastructure`;
  `runtime -> api + application + infrastructure`. `create_app` takes a narrow
  `ApiServices` container declared in `api/`, not `runtime.Services`.
- The worker does not live in `create_app`. FastAPI is a server, not a process manager.
  M3 uses a test harness that runs the app and an `OperationWorker` side by side; M6's
  supervisor hosts both.

## Non-goals

Recorded so they are not later read as omissions.

- No tracking endpoints — submissions, external submissions, recruitment transitions and
  corrections. `TrackingService` already serves the CLI; the endpoints arrive with M5.
- No `cv web`, uvicorn, port probing, or browser opening. M6.
- No React, Vite, or Tailwind. M4.
- No Dashboard projections beyond what the slice needs.
- No retirement of `ARCHITECTURE_DEBT_ALLOWLIST` or `PERSISTENCE_KNOWN_OFFENDERS`: they
  are deliberately-empty exception sets that now also guard the API layer.

## Stages

Focused tests per stage while iterating. **One full Class B gate at the M3 boundary
close**, not one per stage — a stage runs a full gate only if it genuinely closes and is
handed over as an independent boundary.

### A — API foundation, error codes, layering, OpenAPI/TS pipeline

- [x] **A1 — error codes.** `ApplicationError` carries `code`, derived from the class name
      so a new class cannot arrive without one. Explicit `code=` for the codes the
      specification names; declared once in `errors.py` rather than retyped at raise sites.
      The four `IDEMPOTENCY_KEY_REUSED` sites now carry a human message plus the contracted
      code, and the two tests that matched on the prose assert `.code` instead.
- [x] **A2 — the state-record handover.** This file; `CLAUDE.md` and `docs/README.md`
      repointed; superseded banner on `m2-remaining.md`.
- [x] **A3 — leaking builtins, and the consumer audit it forced.** Persistence raised bare `KeyError`/`ValueError` at 63
      sites. Each now raises the taxonomy, classified at the raise site because that is
      the only place that knows which refusal it is: 36 `KeyError` sites were
      `UnknownRecord`, and the 27 `ValueError` sites split across `StateConflict`,
      `LineageBroken`, `PreconditionFailed`, and `ValidationBlocked`. A blanket mapping at
      the service boundary would have collapsed those into one status - notably the ETag
      conflict, which must be 409 rather than 412. Three sites keep `ValueError`
      deliberately: a UnitOfWork built against another database (twice) and a non-positive
      lease, which are caller bugs rather than domain refusals.
      `test_persistence_refuses_through_the_application_taxonomy` derives the rule from the
      AST and fails if an exemption stops matching a real raise.

      **The first evidence run failed here, and the count of broken call sites was 47, not
      the 11 the failures showed.** The taxonomy does not inherit from `KeyError` or
      `ValueError`, so every handler that caught a builtin over a repository call became
      dead code at once. Most were latent: only 11 had a test that noticed. An AST audit -
      55 repository methods that raise the taxonomy, cross-referenced against every
      `try`/`except` over a call to one - found the rest, and it is the reason this was
      repaired by class of behaviour rather than by chasing failures:

      - optional lookups that must still yield `None` (`latest_selection_plan`,
        `active_working_draft`, the chain's decision lookup, an Operation's approved-source
        probe);
      - missing Ready evidence that must still produce a failed qualification rather than an
        exception - 8 sites in `ready.py`, 3 in `chain.py`;
      - missing Operation sources that must still be `SOURCE_CHANGED` - 4 sites, including
        the render handler that also catches `OSError`/`ValueError` from artifact resolution;
      - translations that exist to attach a better message, which now catch the taxonomy and
        re-raise it.

      Six `except ValueError` handlers remain deliberately, none of them over a repository
      refusal: the payload store's own validation, artifact path resolution, invalid stored
      projections, and - twice, and load-bearing - `ApplicationStatus(...)` rejecting an
      unknown status string.

      Four handlers were dead rather than mis-typed and were removed, so nothing implies a
      mapping that no longer happens. Two consequences worth stating: a working-draft
      lineage failure now surfaces as `LineageBroken` (412) rather than `StateConflict`
      (409), and a correction naming another application's event does the same. Both are
      more accurate than the mapping they replace; the edit-version mismatch, which is the
      ETag case, is still `StateConflict` (409).

      A third evidence run found two more, and the miss was in my audit rather than in the
      code: `pytest.raises((KeyError, sqlite3.Error))` puts the exception in a tuple, and
      the audit only read a bare name. Both are now the `UnknownRecord` contract and the
      `sqlite3` import went with them.

      `test_no_test_asserts_a_bare_builtin_from_a_repository` makes that permanent: it
      discovers the repository methods that raise the taxonomy and fails on any
      `pytest.raises` over one that names `KeyError` or `ValueError`, reading **both**
      spellings. Checked by breaking it - run against the previous revision of
      `test_application_contracts.py`, the name-only version reports 0 and the tuple-aware
      version reports exactly the two sites.
- [x] **A4 — config contract.** `api_max_body_bytes` (2 MiB) and `api_dev_origin` in
      `runtime/config.py`, so the limit is recorded where §10 of the test plan requires and
      `cv workspace status` reports it. `build_api_services` reads them.
- [x] **A5 — the `api` package.** `app.py`, `services.py`, `dependencies.py`,
      `problems.py`, `security.py`, `schemas/`, `routers/`. `create_app(ApiServices)` takes
      the narrow container; `runtime.build_api_services` fills it. Problem Details is one
      table keyed by exception class, resolved through the MRO so an unregistered subclass
      inherits its parent's status instead of becoming a 500. `GET /api/v1/health` carries
      the identity pair `cv web` probes plus the version surfaces.

      Both middlewares are raw ASGI rather than `BaseHTTPMiddleware`. Reading the body
      from a `BaseHTTPMiddleware` request consumes the receive channel and leaves the route
      with nothing; the body limit has to read the body, so it buffers and replays it. That
      failure would have been invisible against a 404, so the test drives it over a route
      that echoes what it received.
- [x] **A6 — architecture guard.** `api` registered as a layer:
      `api -> {domain, application, api, util}`, with `runtime`, `infrastructure`, `cli`,
      `sqlite3`, and `playwright` forbidden inside it; `cv_engine.api` forbidden from the
      four inner layers; and `cv_engine.domain` forbidden inside `api/routers/` as the
      derived form of acceptance item 4.
- [x] **A7 — OpenAPI and TypeScript.** `openapi/generate_openapi.py`, `package.json`
      pinning `openapi-typescript` as its only dependency, `README.md`, and the drift test.
      `openapi.json` (OpenAPI 3.1.0, one path) and `types.ts` are generated and committed,
      so a schema change arrives as a reviewable diff the way the frozen SQLite fingerprint
      does. Generation needs no Workspace, database, or provider: only the route table is
      read.
- [x] **A8 — dependencies.** `fastapi>=0.115,<1` in `[project.dependencies]`, and
      `httpx2>=2.12,<3` in the `test` extra for Starlette's `TestClient`.

      `httpx2`, not `httpx`, and the first evidence run is what settled it. Starlette 1.6 -
      the version fastapi 0.141 pins - does `import httpx2 as httpx` in its test client and
      falls back to `httpx` with a deprecation warning naming the supported package. The
      warning was accurate, so the dependency moved rather than the warning being filtered.
      No code changes with it: the test client imports whichever is present under the same
      name, and nothing in this repository imports an HTTP client directly.

      The environment needs `pip install -e '.[test]'` before any API test can run.

Also landed, at the user's request and committed separately so it stays reviewable: a
repository-wide `ruff format` pass over the 26 files that had drifted since TODO 1 defined
the lint/format contract. Formatting only.

**Stage A is closed**, at `b9b1ab3`, on evidence the user ran and accepted.

| Measure | Baseline | Stage A | Delta |
| --- | --- | --- | --- |
| Non-browser suite | 236 passed, 4 deselected | **259 passed, 4 deselected, no warnings** | +23 |
| Collection | 236 | 259 | +23 |

The +23 is accounted for exactly: 19 from `test_api_foundation.py` (12 functions, one
parametrised over the 8 refusals) and 4 new guards in `test_architecture.py`. The final
+1 against the prediction of 258 is the tuple-aware guard added during the third repair
round, and nothing else moved. The environment installed `httpx2` 2.12.0 and the run
carried no warnings, so the deprecation is resolved by the dependency rather than
filtered. The full suite contains all 29 focused cases, so the focused run was not
repeated.

Three rounds of evidence were needed, and what each cost is worth carrying forward:

1. A nested `Request` import that FastAPI could not resolve, because
   `from __future__ import annotations` makes annotations strings that resolve against
   module globals.
2. 47 dead exception handlers, of which the failures showed 11. Deriving the set from the
   code found the other 36; patching the visible ones would have left them latent.
3. Two assertions my own audit could not see, because it read `pytest.raises(X)` and not
   `pytest.raises((X, Y))`. A blind tool reporting zero is worse than no tool, which is
   why the replacement is a committed guard rather than a corrected script.

### B — Applications: create, duplicate-check, read

- [x] Duplicate detection over all three contracts: identical source URL, identical
      normalized-text hash, company/title heuristic. Each match reports which one matched.
- [x] `IngestCommand` gains `client`, `actor_type`, `acknowledged_duplicates`; `ingest`
      stops hardcoding `client="cli"`.
- [x] `create_job_snapshot` records `actor_type`/`client` and appends its audit record in
      the same SQLite transaction as snapshot metadata. `close_application` is complete.
- [x] Duplicate acknowledgement: create always re-runs detection; matches plus
      `acknowledged_duplicates=false` is **412 `DUPLICATE_ACKNOWLEDGEMENT_REQUIRED`** with
      the matches in `context` and **nothing created**; the retry with the flag is 201 and
      still carries the warnings.
- [x] Endpoints, enumerated so completeness is reviewable: application create/list/detail,
      duplicate-check, job-snapshot creation, `GET /applications/{id}/artifacts`,
      `GET /applications/{id}/decision`, and `POST /applications/{id}/close`. No command
      ships without one.

The first closure, at `0374aa5` / `a0c3c34`, was premature: its tests did not prove atomic
snapshot audit, and the endpoint checklist was too general to reveal the missing artifact
and decision reads. Its accepted evidence remains truthful for what it ran; it simply did
not close those two gaps, which is why the repair at `cbc3367` followed.

| Evidence | Result |
| --- | --- |
| Stage B, API foundation, and affected application/Operation contracts | **35 passed** |
| API layering and router architecture guards | **3 passed** |
| OpenAPI and TypeScript regeneration | completed successfully |
| Ruff | passed |
| Pyright | **0 errors, 0 warnings, 0 informations** |
| Diff whitespace check | passed |

The repair adds 2 cases to `test_api_applications.py`: audit-insertion rollback and the two
read endpoints, bringing the file to 11. OpenAPI and TypeScript were regenerated with it.

**Stage B is closed**, at `cbc3367`, superseding the premature closure at `0374aa5` /
`a0c3c34`. The table above stays as the evidence for the pre-repair state, truthful for
what it ran; the repair's own focused handover was never run on its own, and its evidence
is Stage C's instead:

| Evidence for the repair | Result |
| --- | --- |
| `test_api_foundation.py` + `test_api_applications.py`, at Stage C's second run | **30 passed** |
| Non-browser suite, at Stage C's close | **282 passed, 4 deselected** |

The 30 is 19 for the foundation plus 11 for Stage B, which confirms the 11 exactly rather
than by subtraction. The predicted collection of 270 was never observed on its own, and it
did not need to be: 259 + 11 + 12 = 282, so Stage C's accepted number reconciles Stage B's
prediction retrospectively and with no unexplained delta.

One consequence of Stage B reached Stage C rather than Stage B: making an unacknowledged
duplicate a refusal broke two Operation test helpers that ingest the same job text for
every company, and nothing ran `test_operations.py` between the two stages to notice.
Repaired under Stage C at `a7c3425` and `b1b2171`, in the test helpers only - Stage B's
product code is unchanged. It is recorded here because the cause belongs to this stage even
though the failure surfaced in the next one.

### C — Operations surface

- [x] `GET /operations/{id}`, cancel, retry, at `a0116cd`. They return
      `OperationResponse`, which mirrors `OperationView`: the §11 query fields and nothing
      wider. Cancel is `200` because the cancellation is recorded synchronously - running
      work truthfully reports `running` with `cancellation_requested_at` set until it stops
      at its next checkpoint. Retry is `202` with a `Location` naming the **new** Operation;
      `Idempotency-Key` is an optional header, and reusing one returns the Operation it
      already created instead of queueing a second attempt.
- [x] The narrowing lives in the application layer, not the router, at `9d04cfe`.
      `OperationService.get`, `.cancel`, and `.retry` return `OperationView`, produced by
      one shared `as_operation_view`, so a field added to `PersistedOperation` cannot reach
      a client by being added to the subclass. The SQLite adapter's `active_operation` uses
      the same function rather than repeating the narrowing.

      **Observable CLI change, and it is the point rather than a side effect.**
      `cv operation show` and `cv operation cancel` print the client view, so payload,
      sources, lease, attempts, and idempotency key have left that JSON; `cv operation
      retry` narrows the foreground executor's record to the same shape so all three
      subcommands print one shape. `PersistedOperation` has described itself as the
      runner-facing record since M2 and the CLI is a query client, so this realizes the
      documented contract instead of changing it. Everything §11 lists as an Operation query
      field is unchanged.
- [x] One shared `202 + Location` helper for D, E, F, G: `accepted_operation` in
      `api/responses.py`. It sets the status itself rather than leaning on the route's
      `status_code`, because `POST /analyses/{id}/selection-plans` is `201` deterministic
      and `202` for AI proposal mode - one route, two statuses, decided per request. Its
      body is the representation `GET /operations/{id}` returns, so a client can render
      progress from the acceptance response without a second call.

      `API_VERSION` and `API_PREFIX` moved to `api/versioning.py`, re-exported from
      `app.py` so every existing spelling still resolves. The helper builds an Operation
      URL, routers import the helper, and `app.py` imports the routers; two constants in
      their own module break that cycle.
- [x] Test harness running app and `OperationWorker` side by side, in `tests/api_harness.py`
      with the `api_worker` fixture. **Not** in `create_app`, and not a second wiring
      either: it starts the worker the composition root already built, so a passing test
      proves the product's arrangement rather than the harness's. It polls the real
      endpoint rather than the repository, because the polling surface is what a client
      has. Its terminal-status set is derived from `TERMINAL_OPERATION_STATUSES`, so a new
      terminal status cannot leave it waiting for work that has finished.
- [x] `ApplicationStateView.active_operation` typed as `OperationView | None`. The
      projection already received a view and flattened it back into an untyped dict. The
      HTTP mirror is now `OperationResponse | None`, which is what moved the two schemas in
      the OpenAPI diff.

**The first evidence run failed, and it found two defects - one introduced here and one
older.** Repaired at `a7c3425` and `b1b2171`.

1. **`as_operation_view` did not narrow anything.** It handed the record to
   `OperationView.model_validate(record, from_attributes=True)`. A `PersistedOperation`
   already *is* an `OperationView`, so pydantic returned the instance untouched instead of
   building a narrower one. The API then refused its own response with 14
   `extra_forbidden` errors, because `OperationResponse` forbids exactly the runner-only
   fields that were still attached.

   **The same no-op predates Stage C**, in the SQLite adapter's `active_operation`, which
   used that spelling and was believed to return a view. It did not, and the projection
   dumped whatever it got, so `GET /applications/{id}` has been carrying the payload, the
   frozen sources, the lease, and the idempotency key inside `active_operation` since the
   endpoint existed. Typing the field is what exposed it: the leak was invisible while the
   field was `dict[str, Any]` on both sides.

   The repair reads the field set from `OperationView.model_fields` and builds from a
   plain dict, so the two cannot drift and the narrowing cannot silently become an
   identity again. `from_attributes=True` appears nowhere else in `cv_engine`, so this was
   the only instance of the pattern.

2. **Two Operation helpers refused their own second call.** Stage B made an
   unacknowledged duplicate a refusal; both helpers ingest the same job text under a
   different company, and a test that builds two Operations in one Workspace therefore
   hits the second one as a duplicate. This is Stage B's change surfacing in the first run
   of `test_operations.py` since it landed - a test-helper defect, not a product one, and
   the product code Stage B shipped is unchanged.

   **This took two rounds, and the reason is worth keeping.** The first repair fixed
   `_operation_for_runner` because that was the helper the traceback named, and
   `_queued` - the same shape, four callers, one of them calling it twice - was left. A
   name-driven repair found one of two again. The second repair derived the set instead:
   every `ingest` call in the suite, parsed from the AST with its enclosing function and
   whether it acknowledges. That found exactly two helpers; the other 15 sites are
   single-ingest tests, which the full run confirms. Both helpers now share one
   `_ingest_for_operation`, so a third caller cannot reintroduce this.

Worth carrying forward: the assertion that caught the first defect compared the response's
field set against `OperationResponse.model_fields` rather than against a hand-written list.
A list would have been written from the same wrong belief that the narrowing worked.

**Stage C is closed**, at `9d04cfe`, `a0116cd`, `a6d917b`, `a7c3425`, and `b1b2171`, on
evidence the user ran and accepted.

| Measure | Baseline | Stage A | Stage C | Delta |
| --- | --- | --- | --- | --- |
| Non-browser suite | 236 passed, 4 deselected | 259 passed | **282 passed, 4 deselected** | +23 |
| Collection | 236 | 259 | 282 | +23 |

The +23 against Stage A is +11 for Stage B and +12 for Stage C, and the +12 is accounted
for exactly: 9 functions in `test_api_operations.py`, two of them parametrised over 3 and
2. Nothing else moved. The prediction of 282 was made before the first evidence run and
held through both repairs, because neither added or removed a case - they changed one
helper, one narrowing, and one assertion inside tests that already existed. The 4
deselected are still exactly the browser-marked tests, so 282 + 4 is internally
consistent with the 236 / 240 baseline. Same interpreter throughout:
`.venv/bin/python`, Python 3.14.2.

The full non-browser suite is Stage C's whole gate. It contains all 61 focused cases from
the two API files, both of which passed at the previous run, so the focused commands were
not repeated. OpenAPI and TypeScript were regenerated at `a0116cd`; neither repair moves
either file, and the drift test passes inside the suite above.

Two rounds of evidence were needed, and what each cost is worth carrying forward:

1. A narrowing that narrowed nothing, because `model_validate` returns a subclass instance
   untouched. It had been shipping the runner record to HTTP clients since before this
   stage, and only typing the field could expose it.
2. The same helper defect in two places, repaired one at a time because the traceback named
   one. **This is the second time in M3 that a name-driven audit found a subset.** Both
   times the fix was to derive the set from the AST instead. The pattern is now explicit
   enough to expect: when a defect has a shape rather than a location, look for its shape
   everywhere before repairing the instance in front of you.

Nothing in Stage B's product code was reopened. Stage D has not begun.

### D — Analyze, review decisions, deterministic selection plans

**Stage D is closed**, at `1da0003`, `335a476`, `ab1b9e4`, and `16c4c96`, on evidence the
user ran and accepted.

- [x] **The verification came first, and it held.** A successful analyze activation
      already commits the JobAnalysis and its initial deterministic SelectionPlan
      atomically, so this was evidence rather than work and no second mechanism was
      built. `save_analysis` inserts the analysis, the plan, and the Application's
      classification columns inside one `with self.transaction()`; under an Operation the
      repository is bound to the runner's UnitOfWork, so `transaction()` yields that
      connection and the whole activation - both records plus the Operation's own
      completion - commits once. `AnalysisOperationHandler.activate` records both outputs
      as active.

      One thing is outside that transaction and is deliberately left there:
      `set_normalized_role`, which the service calls after `save_analysis`. It is a
      denormalized filing label on `applications`, not one of the two immutable records
      §13 names, and it is recomputed by the next analysis. Under an Operation it joins
      the same UnitOfWork anyway; only the direct CLI path writes it separately.

      The claim is now a test rather than a paragraph. The happy path could not prove it -
      it only shows both rows arrive - so the proof is a failure part-way through: with
      the plan insert refused, no analysis row survives either.
- [x] `POST /applications/{id}/analyses` → **202** through the existing
      `accepted_operation` helper, with `Location` and an optional `Idempotency-Key`. No
      second helper was added. NeedsReview is a successful outcome: the Operation
      succeeds, both immutable records exist, and what needs deciding is reported by the
      Application's review reasons, which name the command that resolves them.
- [x] `apply_analysis_decisions`, at the application layer, branching on what actually
      changed rather than on which fields the client filled in. Meaning changed → one new
      immutable JobAnalysis with its initial deterministic plan, committed by the same
      `save_analysis`. Only the fact overlay changed → one replacement SelectionPlan.
      Both at once → refused, because the new analysis has its own initial plan built from
      a candidate accounting the user has not seen. Neither → refused, because an empty
      submission that created a second identical plan would put a decision in the history
      that nobody made. No existing record is mutated on any branch.
- [x] Deterministic `create_selection_plan` → **201**, synchronous, returning the plan
      itself. The AI `propose_selection_plan` branch of the same route is Stage G and was
      not started; the acceptance helper already sets its own status so that route can
      answer 202 per request without changing shape.
- [x] `POST /analyses/{id}/apply-decisions` and `POST /analyses/{id}/selection-plans`, in a
      new
      `api/routers/analyses.py`. `application_id` is in the body of both rather than
      inferred from the analysis: the client states which Application it believes it is
      deciding for, and a mismatch is a 412 naming the broken lineage instead of a
      decision landing silently on another Application's analysis.
- [x] `Idempotency-Key` moved to `api/headers.py` now that two routers accept it.

**Two product questions were answered before any code was written**, because both fixed
the shape of the OpenAPI contract:

1. **`selected` is an outcome, not an input.** §13 names "selected/excluded/pinned facts";
   the command takes `pinned_fact_ids` and `excluded_fact_ids` only. In a budgeted
   deterministic engine "include this" can only be said as a hold, which is what a pin is,
   and `SelectionManifest.selected_fact_ids` is what the resulting plan reports. The engine
   still owns the final selection and still enforces section budgets, role-block floors and
   required-tag rescue.
2. **Accepting a gap or a low Fit takes the analysis branch.** It is a meaning decision,
   recorded as the analysis override that `derive_review_reasons` already reads to clear
   `LOW_FIT_REQUIRES_ACCEPTANCE` and `HARD_GAP_REQUIRES_DECISION`. No `accepted_gaps`
   field was added to `SelectionManifest`; a second place recording the same state, read by
   nothing, could only drift from the first.

**The overlay is refused, never trimmed.** A fact the Profile never offered, a fact named
on both sides, structure removed as if it were evidence, an exclusion that drops a role
block below the floor it previously reached, and an exclusion that leaves a required tag
with nothing to cover it each raise `SelectionError`, surfacing as 412. The floor and
required-tag guards compare against what the same inputs reached *before* the exclusion
rather than against the floor itself, so a Profile already short for reasons of its own
behaves exactly as it did.

**A third instance of Stage C's narrowing defect was found and fixed here.**
`OperationService.submit_analysis`, `.submit_draft`, and `.submit_render` all returned
`PersistedOperation`. `accepted_operation` builds `OperationResponse`, which forbids
exactly the runner-only fields, so the first analyze submission over HTTP would have been
refused by the API's own response model. Stage C found the same no-op narrowing in
`as_operation_view` and in the SQLite adapter's `active_operation`; this is the third
place, and it is the third time in M3 that the defect had a shape rather than a location.
All three submits now narrow through the one function and the class docstring says why the
narrowing belongs there. Every existing caller reads only `.id`, `.status`, and
`.outputs`, all §11 query fields, so no CLI or test behaviour changes.

Class B: `SelectionManifest.candidates[].reason` can now carry `excluded_by_user`, which it
could not before. Both `build_selection` parameters default to empty and with them empty
every path is the one that ran before, which the first overlay test asserts directly by
comparing the selection and the manifest against a build with no parameters at all.

Commits: `1da0003` (domain overlay), `335a476` (application commands), `ab1b9e4` (API
routes and the narrowing repair), `16c4c96` (tests), `f72dbd4` (route rename).

**One correction, re-evidenced.** The decisions route shipped as
`POST /analyses/{id}/decisions`; §21 spells it `apply-decisions`. §21 does allow final
path names to be an internal design choice while resource identity, explicit source IDs
and use-case semantics hold, so this was not a semantic deviation - but a path that
differs from the document a client reader is holding is a defect regardless of which
clause permits it. Renamed at `f72dbd4` with no alias: the old spelling never reached a
released contract or a frozen record, and an alias the specification does not name would
leave two spellings for one command in the generated types. The rename touches the route,
its four test call sites, two parametrisation ID sets, the analyze route's description,
and both generated files. **OpenAPI and TypeScript were regenerated at `f72dbd4` as well
as at `ab1b9e4`**: 1 path renamed, 1 shared path's description updated, 0 schemas added,
removed, or changed.

Stage D was first marked closed on evidence collected *before* `f72dbd4`, which was
wrong: a rename that moves four test URLs and a route is not covered by a run that
predates it, whatever the reasoning says it cannot have broken. The tables below are the
re-run, after `f72dbd4`, and they are what closes this stage. A gate that already passed
under different conditions is not fresh evidence - this file says so about other people's
work, and it applies here.

OpenAPI and TypeScript were regenerated at `ab1b9e4`. The diff is additive and nothing
moved: 3 paths added, 6 schemas added, 0 removed, 0 existing schemas changed.

| Measure | Baseline | Stage A | Stage C | Stage D | Delta |
| --- | --- | --- | --- | --- | --- |
| Non-browser suite | 236 passed, 4 deselected | 259 passed | 282 passed | **307 passed, 4 deselected** | +25 |

The +25 is accounted for exactly: 16 from `test_api_analyses.py` (14 functions, two
parametrised over 2) and 9 from `test_selection.py` (8 functions, one parametrised over
2). Nothing else moved. The prediction of 307 was made before the first evidence run, held
there, and held again unchanged after the `f72dbd4` rename - which is what a rename that
moves no assertion is supposed to do, and is now measured rather than asserted.
The 4 deselected are still exactly the browser-marked tests, so 307 + 4 stays internally
consistent with the 236 / 240 baseline. Same interpreter as every earlier M3 measurement:
`.venv/bin/python`, Python 3.14.2.

| Focused evidence | Run | Result |
| --- | --- | --- |
| `test_selection.py` — the overlay, its refusals, and no-overlay parity | at `16c4c96` | **17 passed** |
| `test_api_foundation.py` + `test_api_applications.py` + `test_api_operations.py` + `test_operations.py` — the narrowing change's blast radius | at `16c4c96` | **91 passed** |
| `test_api_analyses.py` — the Stage D surface and the atomicity proof | **after `f72dbd4`** | **16 passed** |
| `test_api_foundation.py` + `test_architecture.py` — OpenAPI drift and router layering | **after `f72dbd4`** | **29 passed** |
| Non-browser suite | **after `f72dbd4`** | **307 passed, 4 deselected** |

The 91 is 19 + 11 + 12 + 49, which confirms Stage A's, B's and C's API files unchanged and
puts the whole Operation suite behind the `submit_*` narrowing. The 29 is 19 + 10, and it
is the pair that can actually fail on a renamed route: `test_api_foundation.py` holds the
OpenAPI drift test, so it proves the regenerated contract matches the app after the
rename rather than before it. The two rows measured at `16c4c96` cover files `f72dbd4`
does not touch, and the post-rename non-browser suite contains both of them anyway.

The browser suite was not run: no rendering or browser path is reachable from anything
Stage D touched.

**The first evidence run passed with no repair round**, which had not happened in M3
before - Stage A needed three and Stage C needed two. The difference is where the work
went: the two product questions were settled before the request schemas were written, and
the third instance of Stage C's narrowing defect was found by looking for the *shape*
across all three `submit_*` methods rather than waiting for the analyze route to fail on
it. That is the lesson Stage C recorded, applied once rather than learned again.

Not done in Stage D, and deliberately: no CLI subcommand for either new command. Stage D's
scope is the API surface, the CLI's own analyze path is unchanged, and the deterministic
route still reaches its result with `OPENAI_API_KEY` unset. Stage E names the CLI changes
it needs.

### E — WorkingDraft, ETag, and the corrected validate/approve contract

**Stage E is implemented and awaiting evidence.** Commits `971be7d` (application,
domain, infrastructure, CLI), `91cc6db` (API surface and the regenerated contract),
`76bc471` (tests). Nothing here is closed until the user has run the handover below.

- [x] `generate` (202) at `POST /applications/{id}/working-draft/generate`, through the
      existing `accepted_operation` helper with both source IDs explicit. `GET`/`PATCH`
      with ETag and `If-Match`. `apply_selection_change`, `archive`, `replace` - one
      endpoint each, none of them folded into another.
- [x] **`validate_draft(working_draft_id, expected_version)`** replaces
      `validate_working(application_id)`. `200` including `passed=false`; the immutable
      run is recorded either way; a version the caller no longer holds is `409` rather
      than a report on content the caller is not looking at.
- [x] **`approve_draft(working_draft_id, expected_version, validation_run_id)`.**
      `DraftService.approve` called `_validate_working` *inside* approval, so the four
      binding checks in `state-and-use-cases.md` §15 compared a run against the draft that
      had just produced it: they could not fail. They are real now, and a fifth joined
      them - the run's frozen knowledge context must still be current - because §15 asks
      for it and it is the same class of mistake. The idempotency payload covers all three
      arguments plus the draft's content hash.
- [x] CLI: `cv validate` prints the run ID; `cv approve` resolves the matching run at the
      CLI boundary and refuses, naming `cv validate`, when none matches; `cv fast` chains
      with the real ID. Observable change: `cv approve` alone now requires a prior
      `cv validate`.

**Three decisions taken while writing it**, each of which fixed a contract:

1. **A structured patch is a list of claim edits, applied as one version.** Applying each
   claim as its own version would hand the client a version it never asked about, and
   make a half-applied patch indistinguishable from a completed one. Unauthorized free
   text is kept as a `pending` claim carrying its reason - §14 requires it saved, not
   refused and not discarded - and the result names those claims so a client does not have
   to diff the document to find them.
2. **`update_working_draft` records no ValidationRun.** §15 owns runs. One per autosave
   would fill the record with evidence nobody asked for and make `validated` mean
   "recently saved" instead of "recently checked". The existing `edit_claim` and
   `sync_working_claims` CLI paths keep their own behaviour and were not touched.
3. **A selection change on a manually edited draft is refused, not applied.** The rebuild
   is deterministic, so it would replace the user's own sentences with the engine's - which
   is exactly §14's "requires wording judgment" branch. `manually_edited` decides it in the
   domain from three markers only a human edit path can set: a relinked claim, a `pending`
   claim, and the one derivation `apply_claim_edit` writes.

**Class C**, and it is the only one in Stage E: archived drafts are a new immutable payload
layout, `artifacts/drafts/{application}/{draft}-v{version}.json`, registered as a
`working_draft_snapshot` artifact version. No schema change and no migration, so the frozen
fingerprint does not move; `cv reconcile` verifies the new payloads through the same
inventory as every other one.

**Class B**, both additive: `update_working_draft` takes an optional `selection_plan_id` so
a selection change can repoint the draft in the same write, and `create_selection_plan`
takes an optional repository so a caller can bind it to its own UnitOfWork rather than a
second copy of the overlay existing.

OpenAPI and TypeScript were regenerated at `91cc6db`: 7 paths added, 13 schemas added, 0
removed, 0 existing schemas changed.

**Test call sites moved, and that is the change rather than churn around it.** 18 sites
called `services.drafts.approve(application_id)` and 3 called `validate_working`. They now
go through `approve_active_draft` / `validate_active_draft` in `tests/helpers.py`, which
validate first - which is what every caller must now do. Four of the 18 are inside
`pytest.raises`, and each still refuses at the same place for the same reason: the chain
check and the quarantine check happen before validation would matter, the projection check
belongs to approval, and the failing-report case now surfaces from the binding check rather
than from approval's own run.

**Not done in Stage E, deliberately:** `regenerate_section` and `regenerate_claim` have no
endpoint. They are AI Operations and belong to Stage G; §14 names them as the branch
`apply_selection_change` directs a manually edited draft to, and that refusal names them by
command rather than by route.

#### Handover — focused tests, in sub-stage order

The user runs these. Predictions are stated first so an unexplained delta is a finding.

| Order | Command | What it proves | Pass looks like |
| --- | --- | --- | --- |
| 1 | `.venv/bin/python -m pytest tests/test_api_working_drafts.py` | The whole Stage E surface: generation, ETag, patch, selection change, archive, replace, validate, approve, and the three CLI cases | **23 passed** |
| 2 | `.venv/bin/python -m pytest tests/test_operations.py tests/test_integration.py tests/test_chain_integrity.py` | The blast radius of the approval signature change and of the renamed domain-validator import | **no failures**; these files gain and lose no cases |
| 3 | `.venv/bin/python -m pytest tests/test_api_foundation.py tests/test_architecture.py` | OpenAPI/TypeScript drift against the regenerated contract, and that the new router imports no domain type | **29 passed** |
| 4 | `.venv/bin/python -m pytest` | The Class B gate for the boundary | **330 passed, 4 deselected** |
| 5 | `.venv/bin/python -m ruff check cv_engine tests && .venv/bin/python -m ruff format --check cv_engine tests && .venv/bin/python -m pyright` | Lint, format, and the port/adapter structural check | ruff clean; **0 errors, 0 warnings, 0 informations** |
| 6 | Offline CLI, `OPENAI_API_KEY` unset, fresh Workspace: `ingest → analyze → draft → validate → approve → render → ready → reconcile` | That `cv approve` still reaches an ApprovedRevision after `cv validate`, and that `cv reconcile` verifies the new draft-snapshot payload layout | `validate` prints a `validation_run_id`; `approve` returns a revision whose `validation_run_id` is that one; `reconcile` passes |

The 330 is 307 + 23, and the 23 is exactly the function count of the new file - none of
its cases are parametrised, and no test function was added or removed anywhere else. The 4
deselected are still exactly the browser-marked tests. Same interpreter as every earlier
M3 measurement: `.venv/bin/python`, Python 3.14.2.

The browser suite is not requested. Nothing in Stage E touches a rendering or browser path;
the one flow that ends in a render, `cv fast`, is covered at the seam upstream of the
renderer and its end-to-end case stays browser-marked where it already was.

**Run by the agent, and stated as such:** ruff, ruff format, pyright, OpenAPI generation,
and `npm run generate` were run while writing this. No pytest was run - the counts above
are predictions derived from the source, not measurements.

### F — Render, artifacts, Ready

- [ ] `POST /approved-revisions/{id}/render` → 202.
- [ ] `download_artifact` / `export_recruiter_pdf` as **application** use-cases returning a
      stream descriptor and a safe filename. The router never sees a local path and never
      calls `infrastructure/paths.py`; containment stays that module's single
      implementation, reached through a port.
- [ ] `GET /artifacts/{id}` and `/download`, **by ID only**.
- [ ] Security: traversal, encoded traversal, symlink escape, unregistered ID, hash
      mismatch.
- [ ] The acceptance journey first passes end to end offline here.

### G — AI tasks (§5.3)

- [ ] New **`AIProvider` port in `application/ports/outbound.py`**, one method per
      contracted task. `ClassificationProvider` retires into it — it is named for one task
      and cannot carry five. The existing `AIProvider` protocol in
      `infrastructure/providers.py` is transport, not an application contract, and is
      renamed `StructuredOutputClient` to free the name.
- [ ] `propose_job_analysis` under its contract name. The deterministic domain function
      `classify_job` keeps its name — they are two different things, so there is no
      conflict. Stored provenance names the contract that ran.
- [ ] `propose_selection_plan`, `draft_resume`, `regenerate_section`, `regenerate_claim`
      plus handler registration. The three `OperationType` values already exist and already
      pass the DB CHECK; only registration is missing.
- [ ] Task-contract drift: `ai/contracts/task_contracts.json` is read by nothing while the
      same version is hardcoded in two places and persisted as provenance. Load it or delete
      it.
- [ ] Sanitized raw output as an immutable artifact. No silent fallback.

### H — acceptance and close-out

- [ ] Journeys §5.1–5.4 in full, plus **only the preparation half of §5.5**. §5.5's
      submission bullet needs the submission endpoint and is **deferred to M5** — recorded,
      not quietly skipped.
- [ ] Concurrency, Operations, security, and outcomes-as-data matrices.
- [ ] The complete §6 AI matrix: strict schema generation, per-task Proposal parsing,
      semantic support beyond fact IDs, refusal, invalid output, no silent fallback, raw
      sanitization and artifact registration, exact metadata, stateless/minimal context, one
      transient retry, **zero** retries for schema/business/unsupported-claim/conflict/stale
      source, and the five prompt-injection fixtures. The manual live OpenAI smoke is an M6
      §8.2 release item, not an M3 CI gate.
- [ ] Tick the seven §5.4 boxes in `implementation-plan.md`.
- [ ] Freeze a close-out record under `docs/v2/records/`; close this file out.
- [ ] `CLAUDE.md`'s counterweight: name one control retired, or state why none was
      retirable. Not the two empty exception sets.

## Baseline

Established 2026-08-23, before Stage A implementation. A test count is only comparable to
another count from the same interpreter, so the interpreter is part of the measurement.

| Measure | Value |
| --- | --- |
| Interpreter | `/Users/matanmalka/Projects/resume_python-v2/.venv/bin/python`, Python 3.14.2 |
| Non-browser suite | **236 passed, 4 deselected** |
| Browser-complete suite | **240 passed** |

The two are internally consistent: the 4 deselected are exactly the browser-marked tests,
and 236 + 4 = 240.

The previously recorded figures were 242 / 246. The −6 delta is fully reconciled by the
intervening commits, so it is explained rather than merely noted:

| Change | Delta |
| --- | --- |
| Migration and legacy retirement | −16 |
| Backup coverage | +4 |
| Net schema/migration cleanup | −1 |
| Seed parity | +1 |
| Immutability | +1 |
| Operations coverage | +5 |
| **Net** | **−6** |

Every later prediction in M3 is made against 236 / 240, not against 242 / 246.
