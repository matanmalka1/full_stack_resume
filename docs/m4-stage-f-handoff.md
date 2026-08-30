# M4 Stage F — handoff prompt

Close M4's Stage F gate: the real built-Web end-to-end journey.

## The gap

`frontend/playwright.config.ts` runs `vite preview` — a static build with no FastAPI, no
Operation worker, and no PostgreSQL. The two existing specs (`e2e/shell.spec.ts`,
`e2e/new-application.spec.ts`) cover the application shell and the intake form only, and
all 75 Vitest tests run against a mocked API.

So nothing in the tree proves the built Web talks to the real backend. That is the whole
of this task.

## What to do

Serve the production React build from `cv web` — which already supervises FastAPI, the
worker, and the built assets same-origin on loopback — and point Playwright at it instead
of `vite preview`. Then write the journey.

Open items are in `docs/m4-remaining.md` §F:

1. a real built-Web E2E completing **Create → Analyze → Draft → Edit → Validate → Approve
   → Render → Ready** against FastAPI, the worker, PostgreSQL, the object store, and the
   renderer, with no mocked application services or projections;
2. the journey covers both the review-required and no-review paths;
3. two failure cases: **render failure/retry**, and **old Ready with a newer draft**;
4. Chromium passes;
5. axe passes on New Application, Analysis Review, Draft Editor, Validation, and Ready;
6. the UI explains state, blockers, and next actions without technical IDs, hashes, paths,
   or logs.

Item 3 is deliberately two cases, not eight. Six others were proven where they actually
break — see the reduction note in §F; do not re-add them.

## Constraints

- **Read `CLAUDE.md` first.** It is the whole rule set. In particular: you never run
  tests — hand the user the exact commands and stop for evidence.
- The test database must be a fresh PostgreSQL; the run needs `OPENAI_API_KEY` unset, so
  the journey stays deterministic and offline.
- Do not weaken an existing gate, mock a projection to make a step pass, or add a
  `data-testid` where an accessible name would do.
- Frontend conventions are enforced by the build: generated types from
  `openapi/types.ts`, exhaustive label maps over generated unions, and
  `npm run lint:tokens` with a deliberately empty `EXCEPTIONS` list.
- Everything is Hebrew and RTL, with explicit LTR islands for IDs and technical values.

## Out of scope

Tracking, submissions, fact lifecycle UI, and Dashboard are **M5** and prohibited until
this gate passes — see `docs/m5-remaining.md`. Their APIs already exist; leave them alone.

## Done when

Stage F's six items are checked with observed evidence recorded in `docs/m4-remaining.md`
in the format the other stages use: the exact commands, the counts before and after, and
what each command proves.
