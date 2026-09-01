# M5 — closure and carried-forward work

Status: **closed (2026-08-31).** Recruitment tracking, the contextual Fact lifecycle,
decision-Markdown export, claim editing, Application-detail navigation, amended-posting
capture, and the Application artifact list are implemented in the API and Web UI.
`frontend/todo.md` currently records no remaining frontend task.

This file now lists only work that remains open after M5. Product non-goals are not
repeated here.

## Open work

- [ ] **Full-stack browser E2E.** The current Playwright configuration builds the
      frontend and serves it with `vite preview`; it does not start FastAPI, the worker,
      or an isolated PostgreSQL database. Add a journey that exercises production static
      serving, same-origin API routing, and Operation polling against the real worker,
      with only the AI provider stubbed.
- [ ] **Repository-port hierarchy decision.** Decide whether to keep or flatten
      `DraftRepository -> ReadinessRepository -> TrackingRepository ->
      ApplicationRepository`. Flattening currently duplicates inherited methods; this
      is a deliberate architecture decision, not cleanup.
- [ ] **AI task-contract hashing decision.** Decide whether
      `ai/contracts/task_contracts.json` belongs in `knowledge_context`. It is currently
      stored on provider runs and response artifacts but excluded from
      `Knowledge.versions()`. Adding it would move stored knowledge-context hashes and
      dependent goldens.
- [ ] **Backend-suite reduction, second boundary.** Continue only after a fresh
      redundancy audit. Preserve integrity, immutability, recovery, golden, rendering,
      and deterministic-pipeline evidence.
- [ ] **Path-shaped OpenAPI guard.** `tests/test_api_foundation.py` detects path-shaped
      fields by names such as `*_path`, `*_file`, and `*_location`. It previously missed
      the path-valued `profile_source`; decide how to inspect values or widen the derived
      guard without introducing uncontrolled false positives.

## Closed M5 controls

- [x] The M5 UI/API capabilities and the working-projection data-loss guard are closed.
- [x] The exact Vite development origin is `http://localhost:5173`; foreign mutation
      origins remain refused.
- [x] Reconciliation is exposed as
      `POST /api/v1/maintenance/reconciliations`; CSV export remains application-layer
      functionality without a Web route.
- [x] No milestone control was retired: the generated OpenAPI, exact Origin allowlist,
      immutable payload/approval guards, and deterministic pipeline protect distinct
      failure modes.
