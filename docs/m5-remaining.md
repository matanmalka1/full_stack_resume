# M5 — closure record - 31.09.2026

Status: **closed.** The M5 Web capabilities are implemented and the configured frontend
and non-browser backend gates pass. A browser journey against a real backend remains
next-wave work, recorded under "Deferred, not in M5"; it is not part of this closure.

## Where things are written

One fact, one place.

| Question | Answer lives in |
| --- | --- |
| What M5 delivered and deferred | **this file** |
| Product semantics and UI scope | `docs/spec/product-spec.md` |
| State, action, command, and query contracts | `docs/spec/state-and-use-cases.md` |
| Layer boundaries | `docs/spec/architecture.md` |
| Required evidence | `docs/spec/test-and-acceptance-plan.md` |

## What landed

The system is a FastAPI backend and a React frontend, run as two processes over one
database: `uvicorn cv_engine.runtime.asgi:app` and `python -m cv_engine.worker`. The API
starts no background work; the worker claims queued Operations under a lease.

M5 completed the Web UI for the three capabilities the API already served and added the
projection fields needed to present recruitment history safely.

| Capability | API | Web |
| --- | --- | --- |
| Fact lifecycle | done (`/api/v1/facts`, 10 routes) | done |
| Recruitment tracking | done (5 routes under `/applications/{id}`) | done |
| Provenance export | done (`GET /approved-revisions/{id}/decision-markdown`) | done |
| Claim editing | done (`PATCH /working-drafts/{id}`) | done |

Maintenance has no separate surface:

- **Reconciliation** is `POST /api/v1/maintenance/reconciliations`, behind a
  `MaintenanceService`. It holds the payload store and repository directly, which is why
  it is a service and not a router helper — `ApiServices` carries neither.
- **CSV export** is `infrastructure/exports.py`, projected by
  `application/maintenance.py`. It has no route: §"Deferred, not in M5" keeps CSV Web
  export out of this milestone.

## M5 scope

### Closure verification

The implementation and its boundary evidence are complete.

- [x] Verify the Application-detail recruitment projection: backend-owned direct
      transition choices plus one chronological timeline merging status transitions,
      corrections, next-action changes, and internal/external submissions.
- [x] Verify the React recruitment flow on the Application and Ready screens: transition,
      append-only correction, set/clear next action, external submission without invented
      artifact lineage, and internal submission bound to the displayed revision and PDF.
- [x] Verify the Application list prioritizes the stored recruitment next action and date
      over a preparation-workflow recommendation.
- [x] Verify the contextual fact flow in the draft editor: exact claim capture with
      explicit meaning, tags, and provenance; lifecycle history; explicit confirmation
      and promotion; Profile attachment; and composite confirm-and-use.
- [x] Verify claim capture requires provenance at the HTTP contract and that all fact UI
      request types continue to come from the generated OpenAPI contract.
- [x] Verify Ready shows and downloads the decision Markdown beside its revision, using
      the `Content-Disposition` filename and exposing the content hash only as technical
      evidence.
- [x] Verify approval returns `WORKING_PROJECTION_DIVERGED` for an out-of-band working
      Markdown edit, preserves the edit, creates no ApprovedRevision, and gives the user
      actionable recovery text in the approval dialog.
- [x] Verify the documented development origin exactly matches Vite's configured
      `http://localhost:5173` origin, so intake mutations reach the API while foreign
      origins remain forbidden.
- [x] Close the relevant gates: frontend typecheck and focused unit tests, focused API
      tests, the deterministic no-AI pipeline, then the full non-browser backend suite.

Gate evidence at closure:

- `npm run typecheck` — passed.
- `npm run test` — passed.
- `pytest -q` — **333 passed, 2 deselected** in the configured `not browser` suite. This
  includes `tests/test_pipeline_end_to_end.py`; the two browser-marked tests are the
  explicitly deferred browser boundary below.
- Live origin smoke — the configured Vite origin reached route validation while a foreign
  origin remained `403 ORIGIN_NOT_ALLOWED`.

### 1 — Recruitment tracking UI

Before M5, the Application context screen showed `recruitment_status` read-only. It now
supports the five tracking actions already served by the API:

- [x] Transition status. `applied` is submission-owned and is not offerable: the request
      schema excludes it and the application layer refuses it. Only transitions the
      backend allows may be offered — the graph is narrow, and from `saved` only
      `withdrawn` and `closed` are reachable without a submission.
- [x] Correct a recorded status. Requires the corrected event and a reason; a correction
      appends an event and never edits the one it corrects, so the trail must show both.
- [x] Record an internal submission. Requires the exact ApprovedRevision and PDF artifact
      IDs. Ready qualification is re-derived at submission time, so a stale or tampered
      revision is refused rather than recorded.
- [x] Record an external submission. Invents neither a revision nor an artifact; a field
      that cannot be derived stays null in the UI as well as in the record.
- [x] Set and clear the one active next action. Clearing is a real request, distinct from
      not asking about it.

Surfacing the recruitment timeline is part of this: corrections and submissions are only
meaningful beside the history they amend.

### 2 — Fact lifecycle UI

`docs/spec/product-spec.md` §17 scopes this as a **contextual** flow reached from a draft
claim, not a general Knowledge Manager — the broader Knowledge UI is deferred (§23).

- [x] View facts and one fact's lifecycle trail.
- [x] Create a pending fact. Identity is generated; the UI must not offer a fact ID.
- [x] Capture a fact from an unsupported claim. The claim's exact text becomes the
      rendering, with no AI rewriting; meaning, tags, and provenance are explicit input.
- [x] Confirm, then promote. Explicit confirmation is required for each, and
      `pending -> canonical` in one step is refused.
- [x] Attach a canonical fact to a Profile section.
- [x] `Confirm and use` — one logical command that promotes, attaches, and creates the
      replacement SelectionPlan, or reports a complete failure. The contextual draft UI
      now calls the existing API composite.

### 3 — Provenance export UI

- [x] Offer the decision Markdown beside the revision it explains. The response carries
      `content` and `content_hash`; the suggested save name arrives in
      `Content-Disposition`, not as a body field.

### 4 — runtime constraints to know before touching either process

- **The worker's signal handlers are skipped off the main thread.** `signal.signal`
  raises there, so a caller running the worker in a thread owns the stop event instead.
- **`CV_API_PORT` is not uvicorn's `--port`.** The origin policy allows the origin the
  app believes it answers on, so serving on another port without setting this refuses
  every state-changing request from the app's own UI.
- **The project root is fixed at the installed code location.** Nothing selects it at
  runtime. A test that needs another root injects `AppPaths.from_root(...)` into
  composition; `tests/asgi_factory.py` is what a subprocess-served test loads.

## Frontend conventions this work must hold

Enforced by the build, not by review:

- types come from the generated `openapi/types.ts` through `src/api/contracts.ts`;
  regenerate the contract and the types whenever a route changes;
- a label map keyed by a generated union stays exhaustive, so a value added to the
  backend fails the frontend build rather than arriving untranslated;
- `npm run lint:tokens` refuses literal colors and raw palette utilities, and its
  `EXCEPTIONS` list is deliberately empty;
- the UI is Hebrew and RTL with explicit LTR islands for IDs and technical values;
- no screen requires technical IDs, hashes, paths, or architecture knowledge of the user.

## Known consequence: hand edits to `resume.md`

Nothing imports edits made directly to the working `resume.md` file. Claims are edited
through the draft's own autosave, and the v2 use-case list has no import path.

The data-loss guard **stays**: approval refuses while the projection holds an edit
storage has not imported, because approval rebuilds the projection from the database and
would otherwise destroy that edit without a word. A user who edits `resume.md` by hand
can only re-apply the change in the editor, or regenerate and discard it.

- [x] Surface the refusal in the approval dialog with actionable recovery guidance. The
      projection remains writable, but approval preserves the edit and refuses to create
      an ApprovedRevision until the user resolves it through the editor and revalidates.

## Implementation commits

- `c00276f` — recruitment history and backend-owned transition projection.
- `89a1ed2` — fact provenance and diverged-working-draft protection.
- `bdf65e5` — generated M5 API contract and exposed download header.
- `e8d593c` — typed fact, tracking, and decision-Markdown transports.
- `b21c6ce` — recruitment tracking screens and next-action list priority.
- `58d9b3c` — contextual fact lifecycle and confirm-and-use UI.
- `c54d32d` — Ready submission, decision Markdown, and approval recovery.
- `7bd61f3` — local-origin setup and the milestone checklist.

## Control review

No control was retired. The generated OpenAPI guard, exact Origin allowlist, immutable
payload and approval protections, and deterministic pipeline each protect a distinct
failure mode; the M5 work exercised the Origin and working-projection guards directly,
so removing or weakening one at closure would discard active evidence rather than reduce
redundant process.

## Deferred, not in M5

**Full-stack browser E2E.** Playwright serves a static `vite preview` build, so no
automated test drives the built Web against real FastAPI, a real worker, and a real
database. The seam that carries the risk is production static serving, same-origin
routing, and a real Operation poll against a real worker. The test plan no longer
states it as a met requirement; it is next-wave work, and building it means a
Playwright configuration that starts both processes against a temporary project and an
isolated database, with only the AI provider stubbed.

Two things carry part of that weight today and neither replaces it: the deterministic
pipeline test proves the engine through the application layer, and `live_api_server`
drives a real uvicorn process over a real socket. Both stop short of the browser.

Also deferred, named so they are not rediscovered as gaps: companion application
documents, AI-generated decision explanations, AI-assisted semantic claim linkage, a
broader Knowledge UI, CSV Web export, notifications, calendar integration, analytics,
additional providers, i18n, and hosted or multi-candidate operation
(`docs/spec/product-spec.md` §23).

## Open engineering questions

Not milestone scope; each is a decision to make deliberately rather than a task to pick
up as cleanup.

- [ ] **The port hierarchy is unflattened.** `DraftRepository -> ReadinessRepository ->
      TrackingRepository -> ApplicationRepository` is linear and each level adds its own
      methods, so flattening means duplicating them. The MRO breakage that prompted the
      original split came from base order inside one class, not from depth. Decide
      whether the chain earns its keep; do not refactor it as cleanup.
- [ ] **Whether the AI task contract belongs in `knowledge_context`.**
      `ai/contracts/task_contracts.json` is the single source of contract and prompt
      versions, and both are stored on every provider run and on the registered response
      artifact. They are deliberately **not** in `Knowledge.versions()`, so editing a
      prompt does not stale existing drafts and does not move any
      `knowledge_context_hash`. Adding them would move every stored hash and every golden
      that depends on one. Decide it on its own, with the hash movement stated up front.
- [ ] **Backend-suite reduction, second boundary.** A first pass consolidated duplicated
      evidence across 17 test files without changing production code. Roughly 75 further
      removals remain before the original half-size target is met; continue only through
      a fresh redundancy audit, with integrity, immutability, recovery, golden, and
      rendering failures cut last.

## Cleanup carried forward

- [ ] The path-shaped contract guard in `tests/test_api_foundation.py` matches on field
      *names* (`*_path`, `*_file`, `*_location`, …). `profile_source` was a real
      repository path that the pattern did not match; it was found by reading values, not
      names, and removed from the wire. The guard has a blind spot, and widening the
      pattern has its own false-positive cost — worth a deliberate decision rather than
      leaving it unrecorded.
