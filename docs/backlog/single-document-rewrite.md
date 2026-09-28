# Single-document rewrite — execution plan

Implements [`../decisions/single-document-model.md`](../decisions/single-document-model.md).
Process follows [`../execution-protocol.md`](../execution-protocol.md). Claude is lead and
runs executors as subagents, one git worktree, PostgreSQL database and payload tree per
lane. Three waves; each wave closes green before the next starts.

## Wave 1 — lead alone (foundation and contracts)

Everything the lanes build on. Serial because every later file depends on it.

1. Rewrite `spec/state-and-use-cases.md` (§2–§9, §11, §15–§16, §18, §19, queries).
2. Schema: new Alembic migration dropping `selection_plans`, `working_drafts`,
   `approved_revisions`, `decision_records`, `validation_runs`; creating `cv_documents`;
   restructuring `submissions`; narrowing `artifacts`/`artifact_versions`.
3. Domain: `CVDocument` contract, `document_hash`, `facts_hash`, `basis`, derived states.
4. Application ports for the document store.
5. API contract: `cv_engine/api/schemas/` and the generated `openapi/` plus
   `frontend/src/api/contracts.ts`.

Gate: migration-topology and empty-database upgrade checks with the schema diff stated;
focused domain tests for basis and derived states.

Progress: steps 1–3 landed in session 1 (migration `0002`, `domain/document.py`,
`domain/contracts/document.py`). The dropped tables stay importable as column-only
shapes in `tables/legacy.py` on a detached `MetaData` — a temporary re-export the Wave 2
lanes stop using and Wave 3 deletes. Steps 4–5 landed the same day: `application/ports/documents.py`; `api/schemas/documents.py`
and the reshaped §9 projection and submission schemas; operation types renamed to
`propose_selection` / `render_document`. The API is generated from routes, so
`api/routers/documents.py` declares the document routes now and answers `501` until
Wave 3 wires them — another temporary surface Wave 3 removes. The frontend does not
compile against the new contract until L4 moves it.

From here on these are **lead-only**: `alembic/`, `cv_engine/infrastructure/persistence/tables/`,
`cv_engine/domain/contracts/`, `cv_engine/application/ports/`, `cv_engine/api/schemas/`,
`openapi/`, `frontend/src/api/contracts.ts`, `cv_engine/runtime/composition.py`,
`tests/conftest.py`.

## Wave 2 — four parallel lanes

| Lane | Owns |
| --- | --- |
| **L1 docs** | `docs/spec/product-spec.md`, `docs/spec/architecture.md`, `docs/spec/test-and-acceptance-plan.md` |
| **L2 document core** | `application/state.py`, `application/queries/`, `application/commands/`, `application/ready.py`, `application/chain.py`, `application/knowledge_mutations.py`, `application/services/drafts/`, `application/services/analysis/`; persistence `drafts_sql`, `draft_*_sources`, `draft_lifecycle`, `draft_selection_sql`, `selection_drafts`, `analysis_plans`, `analysis_sources`, `application_projections`, `validation_store`, `decision_store`, `submission_context`, `knowledge_lifecycle`; their tests |
| **L3 render and operations** | `application/services/rendering.py`, `application/services/operations/`, `application/operations.py`, `application/operation_runner.py`, `application/artifacts.py`, `cv_engine/worker/`; persistence `render_context`, `ready_evidence`, `artifacts_sql`, `artifact_catalog`, `provider_evidence`, `operation_*`, `payload_leases`; their tests |
| **L4 frontend** | `frontend/` except `src/api/contracts.ts`; builds against the Wave 1 contract with mocked API |

Before starting, the lead checks the import graph between L2 and L3 persistence files. If
they cannot be made disjoint, L2 and L3 merge into one lane — the protocol forbids shared
files, not fewer lanes.

API routers are not in any lane: lanes test through application services directly.

**Check result (2026-09-28): L2 and L3 merge.** The persistence graph has six cross-lane
edges — `application_projections` → `artifacts_sql`, `operation_sql`;
`draft_approval_sources`, `validation_store`, `decision_store` → `artifacts_sql`;
`ready_evidence`, `render_context` → `drafts_sql` — and both lanes read the unowned
`analysis_sql` (`_lock_application`, `_analysis_record`, `_selection_plan_record`), whose
selection-plan half dies with `selection_plans`. Hoisting helpers into a lead module
would not fix it: `_approved_revision` and the validation/decision helpers in
`artifacts_sql` are deleted by the rewrite, not moved. The application layer is worse:
`services/operations/handlers.py`, `service.py`, `replacement.py` and
`services/rendering.py` call `services/drafts/`, `services/analysis/`, `commands`, `chain`,
`ready` and `queries` — the interfaces L2 is redesigning — so L3 would build on
signatures that do not survive. The backend is sequentially dependent; it runs as one lane.

| Lane | Owns |
| --- | --- |
| **L1 docs** | unchanged |
| **L2 backend** (was L2 + L3) | `cv_engine/application/` except `ports/`; `cv_engine/infrastructure/` except `persistence/tables/`; `cv_engine/domain/` except `contracts/`; `cv_engine/worker/`; `tests/` except `conftest.py`, `tests/architecture/` and the API-level `test_*_api.py`/`e2e/` files, which Wave 3 moves with the routers |
| **L4 frontend** | unchanged |

Inside L2 the order is persistence (document store, file store, submission store against
the Wave 1 ports) → document services (create, selection, edit, check, approve, submit,
build_from_analysis, projection) → operations (propose_selection, draft generation,
render_document, worker handlers). Old modules the lane stops using stay in place for the
Wave 3 deletion unless nothing else in the lane imports them.

Per-lane gate: the lane's focused tests, architecture test with no allowlist growth,
`git diff --stat` inside ownership.

## Wave 3 — lead alone (integration and close)

1. Merge in order L1, L2, L3, L4, with a smoke/import check after each.
2. Routers in `cv_engine/api/`, composition wiring, deletion of dead code (revision
   screens, ApprovedRevision services, `ready.py` leftovers).
3. `CLAUDE.md` immutable-records paragraph; this file closes.
4. Boundary gates, once, over the merged tree: backend focused suites, frontend checks,
   golden hashes and browser tests (rendering changed), and
   `tests/e2e/test_pipeline_end_to_end.py` on a fresh PostgreSQL (stored meanings changed).

## Sessions

Wave 1: one to two sessions. Wave 2: one. Wave 3: one.
