# Candidate Facts Management — Execution Checklist

Status: **Complete**

This checklist is the source of truth for the candidate-facts management task. An item is
checked only after its implementation is complete and the required verification has been
run successfully. Repository policy requires the user to run every test gate, so items
that depend on those gates remain unchecked until the results are reported.

## Scope guard

- MVP: a dedicated `/facts` surface for managing candidate facts through the existing
  `pending -> confirmed -> canonical -> attached` lifecycle, including canonical
  correction by creating a replacement fact.
- The screen is not a general Knowledge Manager. It does not edit Profile definitions,
  policies, prompts, taxonomies, rules, candidate identity, or arbitrary Knowledge files.
- Physical deletion and in-place mutation of canonical facts are out of scope.
- `withdraw`, `retire`, and `known-incorrect` are a later semantic lifecycle phase. They
  must not enter the MVP unless an existing invariant makes an MVP requirement impossible;
  if that occurs, stop and record the blocker here before changing scope.
- Preserve immutable approved/submitted artifacts and historical fact references.

## 1. Specification and contract alignment

- [x] Amend `product-spec.md` minimally to put the dedicated candidate-facts surface in
      scope while retaining the general Knowledge Manager non-goal.
- [x] Amend `state-and-use-cases.md` to document the existing standalone fact reads and
      commands used by the screen: list/detail/history, create pending, confirm, promote,
      attach, and correction through `replaces`.
- [x] State explicitly that canonical correction creates a pending replacement and never
      edits the canonical source fact in place.
- [x] State the MVP/non-MVP boundary for removal: no delete/archive behavior is implied by
      this change; `withdraw`, `retire`, and `known-incorrect` remain deferred decisions.
- [x] Confirm the architecture specification needs no semantic change; update it only if a
      newly required application/query boundary is not already covered.

## 2. Backend query/projection work

- [x] Define the smallest application-layer projection needed to list valid attachment
      targets without exposing Profile files or permitting Profile editing.
- [x] Include stable Profile identifiers, display labels, and section identifiers/labels
      sufficient for an explicit `attach_fact` command.
- [x] Decide from current repository/domain data whether the fact detail must expose its
      existing Profile-section attachments; record and implement this only if required to
      prevent misleading duplicate attachment actions.
- [x] Implement the query through the existing `KnowledgeService`/query boundary.
- [x] Expose the projection through FastAPI with generated-schema-compatible response
      models and no filesystem paths.
- [x] Preserve existing fact mutation behavior and durable-journal invariants.
- [x] Add or extend focused domain/application/API tests for the new projection and any
      changed fact response contract.

## 3. Frontend data layer

- [x] Inspect the actual frontend lint/import configuration and preserve feature boundaries.
- [x] Regenerate or update OpenAPI-derived TypeScript contracts using the repository's
      established workflow; do not hand-maintain generated shapes when generation exists.
- [x] Add attachment-target query keys, API client function, and React Query hook.
- [x] Reuse the existing fact list/detail/create/transition/attach clients and cache refresh
      behavior; do not create a second fact API layer.
- [x] Add focused data/model tests for filtering, selection, replacement-form defaults, or
      other extracted non-visual behavior introduced by the screen.

## 4. Dedicated `/facts` route and UI composition

- [x] Add a dedicated facts page and `/facts` route within the existing `facts` feature.
- [x] Add an appropriate primary-navigation entry without creating a second settings route.
- [x] Compose the page from the existing fact primitives: list, identity, status, detail,
      history, creation form, promotion control, and attachment control.
- [x] Add client-side search/filtering by status, source, and tags unless inspection proves
      server-side filtering is necessary for the current single-candidate data size.
- [x] Support direct selection/deep-linking of a fact so Draft Editor can link to the exact
      record without requiring users to know a fact ID.
- [x] Adapt the create form so its audit reason describes the facts page rather than the
      contextual draft panel.
- [x] Add a canonical-correction action that opens the reused create form with explicit
      replacement context and sends `replaces=<original fact id>`.
- [x] Keep lifecycle attestations explicit for confirmation and promotion.
- [x] Allow attachment only after canonical promotion and only to a target returned by the
      attachment-target projection.
- [x] Show existing attachments if the backend projection is included, and avoid presenting
      an already-attached target as a new meaningful action.
- [x] Provide loading, empty, error, reconciliation-blocker, success, keyboard, and Hebrew
      RTL states consistent with existing UI primitives.
- [x] Add focused React tests for list/detail selection, create, confirm/promote, correction,
      attachment, deep links, and failure states.

## 5. Settings and Draft Editor integration

- [x] Replace the read-only Fact Pool card in Settings with a concise candidate-facts
      summary/link while leaving reconciliation and execution settings in Settings.
- [x] Keep claim-specific fact capture and `confirm-and-use` behavior in Draft Editor.
- [x] Remove or reduce the duplicate general lifecycle browser in Draft Editor.
- [x] Add a link from Draft Editor to the exact fact on `/facts` where a fact-specific
      management action belongs on the dedicated screen.
- [x] Verify Draft Editor still receives every contextual capability required to resolve
      unsupported claims and build a replacement SelectionPlan.
- [x] Extend the closest Settings and Draft Editor tests rather than duplicating coverage.

## 6. MVP verification and cleanup

- [x] Review the final diff for accidental changes to fact semantics, Profile editing,
      generated artifacts, or the unrelated pre-existing worktree modification.
- [x] Confirm no new `withdraw`, `retire`, `known-incorrect`, delete, or canonical in-place
      update path entered the MVP.
- [x] Confirm touched source files respect repository size/import/UI conventions and remove
      obsolete exports/components only when no consumer remains.
- [x] Provide focused backend test commands for the user to run and record their results.
- [x] Provide focused frontend test/lint/type-check commands for the user to run and record
      their results.
- [x] Because the API response/projection contract changes, provide the deterministic
      no-AI fresh-PostgreSQL pipeline command required by `AGENTS.md` and record its result.
- [x] Provide the boundary non-browser suite command once, after the focused gates, and
      record its result.
- [x] Provide the browser suite command if the final diff changes a rendered artifact path
      or rendering behavior; otherwise record that the browser gate is not triggered.
- [x] Update product/developer documentation for the final route and responsibility split.
- [x] Verify the explicitly authorized null-safety correction in
      `features/applications/model/analysisViewState.ts` with typecheck, strict lint, and
      its focused model test.
- [x] Mark this checklist `Complete` only after all required user-run gates pass and no
      required work remains.

## 7. Deferred lifecycle phase — not part of MVP

- [ ] Specify distinct semantics for withdrawing an unverified fact, retiring a formerly
      relevant canonical fact, and marking a fact known incorrect.
- [ ] Specify effects on Profile pools, selection, draft staleness, warnings, validation,
      audit history, reconciliation, and immutable historical revisions.
- [ ] Decide whether disposition is represented by additional statuses or an orthogonal
      lifecycle field/event; include migration and compatibility consequences.
- [ ] Implement domain, KnowledgeStore staging, durable journal, application commands,
      API, projections, frontend controls, and required regression coverage only after the
      semantic design is explicitly approved.

## Verification commands and recorded gates

Run from `/Users/matanmalka/Projects/resume_python-facts-management` in this order.
Do not mark the related implementation items complete until these commands pass.

1. Focused Python formatting/static and Facts tests:

   ```bash
   ../resume_python/.venv/bin/ruff check cv_engine/api/routers/facts.py cv_engine/api/schemas/facts.py cv_engine/application/commands cv_engine/application/services/knowledge tests/test_api_facts.py tests/test_fact_lifecycle.py
   ../resume_python/.venv/bin/pyright
   ../resume_python/.venv/bin/python -m pytest -q tests/test_fact_lifecycle.py tests/test_api_facts.py tests/test_api_foundation.py
   ```

2. Focused frontend contracts, lint, and unit tests:

   ```bash
   cd frontend
   npm run typecheck
   npm run lint:tokens
   npm run lint:strict
   npm run test -- src/features/facts src/features/settings/pages/SettingsPage.test.tsx src/features/drafts/pages/DraftEditorPage.test.tsx src/app/workflowRoutes.test.tsx
   cd ..
   ```

3. Public-projection deterministic pipeline gate, with AI explicitly unavailable:

   ```bash
   env -u OPENAI_API_KEY ../resume_python/.venv/bin/python -m pytest -q tests/test_pipeline_end_to_end.py
   ```

4. Boundary non-browser suite, once after the focused gates:

   ```bash
   ../resume_python/.venv/bin/python -m pytest -q
   ```

The browser/golden gate is not triggered: the diff changes no renderer, template,
artifact path, HTML/PDF output, or golden hash. No Alembic/schema gate is triggered.

## Progress log

- 2026-09-10: Checklist created before implementation. Deferred lifecycle work separated
  from the MVP. No implementation or test execution performed yet.
- 2026-09-10: Moved the task to worktree
  `/Users/matanmalka/Projects/resume_python-facts-management` on branch
  `codex/facts-management`; the original worktree's pre-existing modification was left
  untouched.
- 2026-09-10: Updated the product and use-case specifications. Architecture already places
  fact reads and attachment mutations in `KnowledgeService`, so no architecture amendment
  is required for the read-only attachment-target projection.
- 2026-09-10: Implemented the attachment-target projection/API, regenerated OpenAPI and
  TypeScript contracts, composed `/facts`, moved general lifecycle management out of
  Settings and Draft Editor, preserved contextual claim capture/confirm-and-use, and added
  focused backend/frontend coverage. Implementation checkboxes remain open until the user
  runs the required gates above.
- 2026-09-10: Static diff review and `git diff --check` passed. Added two backend test
  functions and nine frontend test cases; extended the closest Settings and Draft Editor
  tests. No test suite, lint gate, type-check gate, or pipeline gate was run by the agent.
- 2026-09-10: User ran the focused backend tests: 47 passed. Ruff reported two scoped
  import-order errors and Pyright reported one scoped attachment-profile type error; all
  three were corrected. Frontend typecheck/lint reported scoped `/facts` findings, which
  were corrected. Full frontend typecheck also reports a pre-existing error in
  `features/applications/model/analysisViewState.ts`, a file unchanged by this branch;
  that unrelated error remains outside this task unless the user explicitly expands scope.
- 2026-09-10: User reran backend verification after the fixes: focused Facts/API/Foundation
  tests passed (47 passed) and Pyright passed with 0 errors, 0 warnings. Ruff found one
  remaining import-order issue in `application/commands/knowledge.py`; the import was
  reordered and awaits the narrow Ruff rerun.
- 2026-09-10: User confirmed the narrow Ruff rerun passed. Backend focused verification is
  complete: Ruff passed, Pyright passed, and 47 tests passed.
- 2026-09-10: Frontend design-token and strict lint gates passed. Typecheck found two
  scoped compatibility/test-typing errors plus the unchanged `analysisViewState.ts`
  baseline error. Focused Vitest ran 71 cases: 68 passed and three new `FactsPage` tests
  failed because their queries assumed unique duplicated text or a specific error title.
  The scoped type errors and test assertions were corrected; frontend verification awaits
  rerun.
- 2026-09-10: The focused frontend rerun passed 70 of 71 tests. The remaining failure was
  a test race: the assertion queried the attachment button after fact detail loaded but
  before the independent attachment-target query completed. The test now awaits the
  button; a focused rerun is required. Strict lint passed. Typecheck now reports only the
  unchanged pre-existing `features/applications/model/analysisViewState.ts` error.
- 2026-09-10: User reran the focused frontend suite after the timing fix: all 8 test files
  and all 71 tests passed. Frontend MVP implementation items are verified. The aggregate
  frontend gate remains open because full typecheck is still blocked solely by the
  unchanged pre-existing `features/applications/model/analysisViewState.ts` error.
- 2026-09-10: User ran the deterministic no-AI pipeline gate: 3 tests passed. The boundary
  non-browser suite then passed with 538 tests and 2 deselected. Final MVP scope review and
  `git diff --check` passed; no deferred fact lifecycle or destructive fact operation was
  introduced.
- 2026-09-10: User explicitly expanded scope to fix the pre-existing frontend type error.
  `analysisViewState` now narrows `latest_analysis` before reading its timestamp, preserving
  existing behavior. User confirmed typecheck, strict lint, and the focused model test all
  passed. The MVP checklist is complete; section 7 remains deliberately deferred and is not
  part of this delivery.
