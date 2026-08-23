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

**The focused Stage B repair is implemented and awaiting new user evidence.** The earlier
closure at `0374aa5` / `a0c3c34` was premature: its tests did not prove atomic snapshot
audit, and the endpoint checklist was too general to reveal the missing artifact and
decision reads. The accepted evidence remains truthful for what it ran, but it does not
close these two gaps.

| Evidence | Result |
| --- | --- |
| Stage B, API foundation, and affected application/Operation contracts | **35 passed** |
| API layering and router architecture guards | **3 passed** |
| OpenAPI and TypeScript regeneration | completed successfully |
| Ruff | passed |
| Pyright | **0 errors, 0 warnings, 0 informations** |
| Diff whitespace check | passed |

The repair adds 2 cases to `test_api_applications.py`: audit-insertion rollback and the two
read endpoints. Its 11 cases make the predicted next non-browser collection **270**:
Stage A's 259 plus Stage B's 11. OpenAPI/TypeScript have been regenerated. Stage B remains
open until the user runs and accepts the focused handover; the full non-browser suite
remains the M3 boundary gate. Stage C has not begun.

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
older.** Repaired at `a7c3425` and `<repair2>`; Stage C is awaiting a clean run.

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

The collection prediction held exactly. The second run collected **282** and reported
`1 failed, 281 passed, 4 deselected`, against a predicted 282 and a baseline of 236 / 240;
the single failure was defect 2's second helper and nothing else moved. `test_api_*`
passed in full at that run: 61 for the Stage C pair and 30 for the Stage A/B pair.

OpenAPI and TypeScript were regenerated; the entry-level diff is in `a0116cd`, and neither
repair moves either file. Nothing in Stage B's product code was reopened, and Stage D has
not begun.

Predicted next non-browser collection: **282** - Stage B's 270 plus the 12 cases in
`test_api_operations.py` (9 functions, two of them parametrised over 3 and 2). No test was
removed, and the repair adds no case: it changed one helper and one assertion inside
existing tests. Two existing assertions in `test_operations.py` moved with the contract
without changing the count either: the detail projection is compared against the view, and
the cancel/retry immutability assertion reads the stored record once so it still compares
the whole row.

### D — Analyze, review decisions, deterministic selection plans

- [ ] `POST /applications/{id}/analyses` → 202. NeedsReview is a successful outcome.
- [ ] **Verify first**, then record: does a successful analyze activation already commit the
      initial deterministic SelectionPlan atomically? `PreparedAnalysis.plan_manifest`
      suggests it does. If so this is evidence, not work.
- [ ] `apply_analysis_decisions`; deterministic `create_selection_plan` (201).

### E — WorkingDraft, ETag, and the corrected validate/approve contract

- [ ] `generate` (202), `GET`/`PATCH` with ETag and `If-Match`, `apply_selection_change`,
      `archive`, `replace`.
- [ ] **`validate_draft(working_draft_id, expected_version)`** replaces
      `validate_working(application_id)`. 200 including `passed=false`.
- [ ] **`approve_draft(working_draft_id, expected_version, validation_run_id)`.** Today
      `DraftService.approve` calls `_validate_working` *inside* approval, so it creates its
      own ValidationRun and the four binding checks in `state-and-use-cases.md` §15 are
      vacuous. This is a correctness gap in existing code, not only an API concern. The
      idempotency payload hash covers all three arguments plus the draft content hash.
- [ ] CLI: `cv validate` prints the run ID; `cv approve` resolves the matching run at the
      CLI boundary and refuses, naming `cv validate`, when none matches; `cv fast` chains
      with the real ID. Observable change: `cv approve` alone now requires a prior
      `cv validate`.

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
