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
- [ ] **A3 — leaking builtins.** Repositories raise bare `ValueError`/`KeyError`, which the
      CLI catches wholesale and the API cannot. `raise ValueError("working draft edit
      version mismatch")` in `persistence/drafts.py` *is* the ETag-conflict path and must be
      409, not 500. Translate at the service boundary into `StateConflict`/`UnknownRecord`,
      with CLI messages and exit codes unchanged.
- [ ] **A4 — config contract.** `api_max_body_bytes` (2 MiB) and `api_dev_origin` added to
      `runtime/config.py`, so the chosen body limit is recorded where §10 of the test plan
      requires and `cv workspace status` can report it.
- [ ] **A5 — the `api` package.** `app.py` (`create_app(services: ApiServices)`),
      `services.py`, `dependencies.py`, `problems.py`, `security.py`, `schemas/`,
      `routers/`. Problem Details as one mapping table, no message parsing. Body limit,
      Origin validation, non-wildcard CORS. `GET /api/v1/health` carrying the §17 version
      surfaces.
- [ ] **A6 — architecture guard.** `test_architecture.py` has no `api` layer today.
      Register it; forbid `runtime`/`infrastructure`/`cli`/`sqlite3`/`playwright` inside
      `api`; forbid `cv_engine.api` from the inner layers; and forbid `cv_engine.domain`
      inside `api/routers/` as the derived form of acceptance item 4.
- [ ] **A7 — OpenAPI and TypeScript.** `openapi/` at the repo root with `openapi.json`,
      `types.ts`, `package.json`, lockfile. A Python drift test regenerating the schema from
      `create_app`, and an `npm ci && npm run generate && git diff --exit-code` check.
- [ ] **A8 — dependencies.** `fastapi` in `[project.dependencies]`, `httpx` in the `test`
      extra. Not installed in `.venv` yet; the environment needs a reinstall before any API
      test can run.

### B — Applications: create, duplicate-check, read

- [ ] Duplicate detection over all three contracts: identical source URL, identical
      normalized-text hash, company/title heuristic. Each match reports which one matched.
- [ ] `IngestCommand` gains `client`, `actor_type`, `acknowledged_duplicates`; `ingest`
      stops hardcoding `client="cli"`.
- [ ] `create_job_snapshot`, `close_application`.
- [ ] Duplicate acknowledgement: create always re-runs detection; matches plus
      `acknowledged_duplicates=false` is **412 `DUPLICATE_ACKNOWLEDGEMENT_REQUIRED`** with
      the matches in `context` and **nothing created**; the retry with the flag is 201 and
      still carries the warnings.
- [ ] Endpoints, including `POST /applications/{id}/close`. No command ships without one.

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
