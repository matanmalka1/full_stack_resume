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
- [x] `create_job_snapshot`, `close_application`.
- [x] Duplicate acknowledgement: create always re-runs detection; matches plus
      `acknowledged_duplicates=false` is **412 `DUPLICATE_ACKNOWLEDGEMENT_REQUIRED`** with
      the matches in `context` and **nothing created**; the retry with the flag is 201 and
      still carries the warnings.
- [x] Endpoints, including `POST /applications/{id}/close`. No command ships without one.

**Stage B implementation is complete and awaiting the user's focused evidence.** It adds
9 tests in `test_api_applications.py`, so the predicted non-browser collection after
acceptance is **268**: Stage A's 259 plus exactly 9. The tracker does not close Stage B or
record a passing count until the user runs and accepts the handover commands. Stage C has
not begun.

### C — Operations surface

- [ ] `GET /operations/{id}`, cancel, retry. Return `OperationView`, not
      `PersistedOperation`.
- [ ] One shared `202 + Location` helper for D, E, F, G.
- [ ] Test harness running app and `OperationWorker` side by side. **Not** in `create_app`.
- [ ] `ApplicationStateView.active_operation` typed as `OperationView | None`.

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
