# Task: close M4 — prove the Web UI reaches Ready

Repository: `resume_python`, branch `main`. Read this fully before touching anything.

## 0. Where things stand

Recent work (all merged, all green) replaced persistence with PostgreSQL + SQLAlchemy 2.0
Core + Alembic, put immutable payloads behind an object-storage abstraction (local default,
S3/R2 supported), and separated secrets from configuration.

`CLAUDE.md` and `docs/v2/spec/architecture.md` are current. Older documents that still
describe SQLite or a local-only system are superseded on those subjects; **do not stop to
report that contradiction.**

Baseline: **341 backend tests**, 156 frontend tests. `docs/v2/smoke-run.md` reaches
`preparation_state: ready` offline via the **CLI**.

## 1. The problem

The CLI is proven end to end. **The Web UI is not.**
`docs/v2/m4-remaining.md` has six acceptance items still open:

```
[ ] A real built-Web E2E completes Create through Ready against FastAPI + worker + DB
[ ] The journey covers review-required and no-review paths
[ ] The central failure matrix: unsupported edit, validation block, stale validation
[ ] Chromium full E2E and central WebKit smoke pass
[ ] axe passes on New Application, Analysis Review, Draft Editor, Validation, Ready
[ ] The UI explains state, blockers, and safe next actions without technical IDs
```

`frontend/e2e/` holds only `new-application.spec.ts` and `shell.spec.ts`. Nothing walks
the full chain.

Two suites have also not run in a long time and may already be red:

- `pytest -m browser` — 2 tests, always deselected by the default gate. One of them
  (`tests/test_integration.py:223`) had its assertion changed during the object-storage
  work and has never been executed since.
- `npm run e2e` — Playwright, not run recently.

`CLAUDE.md` is explicit that the Web/API vertical slice must reach Ready with its central
failure paths passing before further UI work. Auth, tenancy, and deployment are all
queued behind this, and every one of them will build on the Web UI. A defect found after
they land becomes "is this new, or was it always broken?" — which is exactly what the CLI
smoke run exists to prevent, and the Web UI has no equivalent.

## 2. Start here — measure before building

Run the two suites that have not run, and report what you find **before** writing any new
test. If either is red, fixing it comes first; a new E2E built on a broken foundation
proves nothing.

```bash
./.venv/bin/python -m pytest -m browser
cd frontend && npm run e2e
```

These need a running PostgreSQL (`docker compose up -d postgres`) and Chromium
(`./.venv/bin/playwright install chromium`).

**This is the highest-value step in the task. Do it first and stop to report.**

## 3. Then close the gap

In priority order:

1. **One E2E that walks Create → Ready** through the real UI against FastAPI, the
   Operation worker, and PostgreSQL. The deterministic path, no AI key. This is the
   single most valuable missing test.
2. **The no-review and review-required branches** of that journey.
3. **The central failure matrix** — unsupported edit, validation block, stale validation.
4. **axe** on the five named screens.

Stop after each and report. Do not attempt all four in one pass.

## 4. Rules

- **You do not run the full backend or frontend suite** — the user runs those. You may
  run the two E2E/browser suites above (that is the point of the task), plus `ruff`,
  `pyright`, `tsc --noEmit`, `grep`, and targeted single-test runs while debugging.
- **Do not refactor unrelated code.** `DraftEditorPage.tsx` (539 lines) and
  `OperationPage.tsx` (418) are known debt; leave them.
- **Do not start auth, tenancy, CORS, or deployment work.**
- **Do not change product behaviour to make a test pass.** If the UI genuinely cannot
  explain a blocker without showing a technical ID, that is a finding — report it.
- **Stop and ask** when a test would need a behaviour change, when an acceptance item
  cannot be honestly ticked, or when a failure looks like a real defect rather than a
  missing test.

## 5. Acceptance

1. `pytest -m browser` passes, or its failures are reported and understood.
2. `npm run e2e` passes, or the same.
3. A Chromium E2E completes Create → Ready against the real stack.
4. `docs/v2/m4-remaining.md` is updated with what landed and what remains — it is the
   active tracker. Do not edit anything under `docs/v2/records/` or the frozen
   `m2/m3-remaining.md`.

## 6. Reporting

Never claim completion with "implemented" alone. Report what passed, what failed, and
what remains; a hard failure is never relabelled a warning. Hand back the ordered
commands with what each proves, the expected counts against the 341 / 156 baselines with
every deviation explained, and state plainly anything you could not verify.
