# M4 — remaining work

Status: **M4 in progress** (started 2026-08-24). Authority for scope and gates is
`docs/v2/spec/implementation-plan.md` §6. M3 is closed; its evidence remains frozen in
`docs/v2/records/m3-acceptance.md`.

## Where things are written

One fact, one place. This file is the only record of current M4 state.

| Question | Answer lives in |
| --- | --- |
| What is done, what remains, what is blocked | **this file** |
| Product semantics and UI scope | `docs/v2/spec/product-spec.md` |
| State, action, command, and query contracts | `docs/v2/spec/state-and-use-cases.md` |
| Frontend dependency and layer boundaries | `docs/v2/spec/architecture.md` |
| Required Web evidence | `docs/v2/spec/test-and-acceptance-plan.md` |
| Closed M3 state and evidence | `docs/v2/m3-remaining.md`, `docs/v2/records/m3-acceptance.md` |
| Non-milestone cleanup | `docs/v2/cleanup-todos.md` |

## Boundary and sequence

M4 implements the already-proven API workflow through a Hebrew, desktop-first Web UI:

`Create -> Analyze -> Review if required -> Draft -> Edit -> Validate -> Approve -> Render -> Ready`

Work stays serial in this worktree. The implementation order is:

1. design pass;
2. frontend foundation;
3. intake and analysis/review;
4. editor and preview;
5. validation, approval, rendering, and Ready;
6. central failure paths, accessibility, browser coverage, and the M4 gate.

Dashboard, tracking, submission, and Application Detail are M5 work and remain prohibited
until the complete M4 gate passes. `cv web`, browser launch, port supervision, and Node-free
runtime packaging remain M6 work. Development may use Vite and FastAPI directly; M4 still
adds the production build/static-serving integration required by §6.2.

## A — Design pass

**Stage A is complete as a design boundary.** It defines the information architecture,
low-fidelity layouts, direction rules, visual hierarchy, focus behavior, and responsive
fallback required before component implementation. There is no runtime evidence yet because
the frontend does not exist.

- [x] **A1 — state handoff.** Open this tracker and repoint the living documentation and
      repository authority to M4 without modifying M3's frozen record.
- [x] **A2 — one workflow shell.** Use a shallow shell with the current Application context,
      a progress landmark, one primary content region, and local actions. Do not introduce
      Dashboard navigation or expose technical IDs in the normal flow.
- [x] **A3 — visual foundation.** Define typography, spacing, restrained color, focus,
      warning/blocker, and status hierarchy below.
- [x] **A4 — direction and responsive behavior.** Define an RTL application shell, explicit
      LTR islands, the desktop editor/preview split, and a single-column fallback below.
- [x] **A5 — complete low-fidelity flow.** Cover intake, optional review, editing, validation,
      explicit approval, rendering, Ready, Settings, and the central conflict/failure surfaces.

### A.1 Interaction and information architecture

The backend projection is authoritative. React renders `preparation_state`,
`working_draft_state`, `review_reasons`, `warnings`, `active_operation`,
`available_actions`, `blocked_actions`, `recommended_action`, and
`newer_draft_in_progress`; it does not infer a second workflow state machine.

The shell has three persistent regions:

1. a compact header with product name, current company/role when an Application exists,
   and Settings;
2. an ordered workflow landmark showing completed, current, and future stages without
   making future stages navigable when their action is blocked;
3. one page-level main region with a single emphasized primary action.

Operation Progress is a workflow state in the main region rather than a global modal. This
keeps phase, cancellation, failure, retry, and deterministic-continuation choices readable
and preserves the browser Back behavior. Dialogs are reserved for explicit trust boundaries:
approval confirmation, autosave conflict resolution, and destructive-to-working-copy choices.

### A.2 Visual foundation

| Concern | Decision |
| --- | --- |
| Typography | Native system sans-serif stack; 16px body, 14px supporting text, 20/24/32px headings; document preview keeps its server-rendered typography. |
| Spacing | 4px base; common gaps 8/12/16/24/32px; content width capped for reading while the editor may use the full desktop width. |
| Surfaces | Neutral canvas, white primary surface, one subtle border level; shadow only for a dialog/popover. |
| Accent | One restrained blue for the primary action, current step, links, and focus support; color is never the only status signal. |
| Success | Green plus icon/text for completed validation and Ready. |
| Warning | Amber plus a visible `אזהרה` label; warnings never look like blockers and never silently disable approval. |
| Blocker | Red plus a visible `חסימה` label, plain-language reason, and the allowed resolution action when one exists. |
| Focus | A 2px high-contrast focus ring with 2px offset on every interactive element; focus is moved to the page heading after route changes and to the dialog heading when a dialog opens. |
| Status | Text label + icon + position in the workflow landmark. Technical codes may appear only in expandable details when useful. |
| Motion | Minimal progress indication; honor reduced-motion preferences and never depend on animation to communicate completion. |

The implementation expresses these as semantic tokens rather than scattering literal colors
and spacing values through components.

**Contrast is checked and closed.** Every token pair the components actually produce was
measured against WCAG 2.1 (4.5:1 for text, 3:1 for the focus ring and for a control edge
that is the only boundary of the control). Nineteen pairs were measured; the lowest passing
text pair is `cv-success` on `cv-surface` at 5.87:1, and the tinted `tone/10` and `tone/5`
callout and badge surfaces keep their own text at 5.10:1 or better.

One pair failed: `cv-border` on `cv-surface` at **1.38:1**. The token was not weakened for
decoration it serves correctly. Instead `--color-cv-border-strong` (`#818b9a`) was added for
control edges — 3.45:1 on `cv-surface`, 3.22:1 on `cv-canvas`, 3.04:1 on `cv-surface-muted` —
and text inputs, textareas, selects, and checkboxes use it. `cv-border` remains the card and
separator line, where no 1.4.11 obligation applies.

### A.3 Direction rules

- The document root and application shell use `dir="rtl"` and Hebrew labels.
- URLs, hashes, IDs, filenames, ETags, error codes, English job/CV text, and log references
  use explicit `dir="ltr"` with `unicode-bidi: plaintext` or isolation as appropriate.
- Mixed user text uses `dir="auto"`; claim controls remain in the RTL shell even when the
  claim itself is LTR.
- The server-rendered preview owns its own document direction inside a sandboxed iframe.
  Shell direction and preview direction never leak into one another.
- Logical CSS properties (`margin-inline-*`, `padding-inline-*`, `start`, `end`) are preferred
  over physical left/right rules.

### A.4 Low-fidelity wireframes

Numbers identify regions; exact Hebrew labels and behavior follow each frame.

#### 1. New Application and duplicate precheck

```text
+--------------------------------------------------------------------------+
| [1 Product]                                            [2 Settings]       |
|--------------------------------------------------------------------------|
| [3 Workflow: New application > Analysis > Draft > Validation > Ready]    |
|--------------------------------------------------------------------------|
|                         [4 Page heading]                                 |
|  [5 Company]                       [6 Target role]                        |
|  [7 Optional source URL]                                                   |
|  [8 Job text / browser-read .txt fills this editable area]               |
|  [9 Duplicate warning and choices, only when candidates exist]           |
|                                             [10 Primary: Create]          |
+--------------------------------------------------------------------------+
```

- Heading: `משרה חדשה`; primary action: `יצירת מועמדות`.
- Choosing a `.txt` file reads it locally into the text area; the browser does not upload
  the file. The URL is provenance only and is never presented as an import action.
- Duplicate results are non-blocking. Each result offers `פתיחת המועמדות הקיימת`; a separate
  explicit `יצירה בכל זאת` continues with the entered content.
- After creation, `ניתוח המשרה` is a separate action. Creation never implies an AI call.

#### 2. Operation Progress and Analysis Review

```text
+--------------------------------------------------------------------------+
| [1 Application context]                                  [2 Settings]    |
|--------------------------------------------------------------------------|
| [3 Workflow landmark: current stage announced]                           |
|--------------------------------------------------------------------------|
| [4 Operation heading]                                                     |
| [5 Current phase]                                      [6 Elapsed state] |
| [7 Progress/status live region]                                           |
| [8 Safe explanation; optional expandable technical details]              |
| [9 Cancel when available]                          [10 Retry/Continue]    |
+--------------------------------------------------------------------------+

+--------------------------------------------------------------------------+
| [1 Review heading + plain-language reason summary]                        |
| [2 Reason navigation]       | [3 Decision form for selected reason]       |
| - Ambiguity                 | - Interpretation / accepted gap             |
| - Fit or hard gap           | - Relevant facts and evidence               |
| - Fact selection            | - Pending fact resolution when applicable   |
| [4 Effects summary: all decisions create one immutable replacement]       |
| [5 Back]                                  [6 Apply all decisions once]    |
+--------------------------------------------------------------------------+
```

- Operation status is announced through a polite live region. Polling does not steal focus.
- A provider failure offers `ניסיון חוזר` and, only where the backend exposes it, an explicit
  `המשך במצב דטרמיניסטי`; there is no silent fallback.
- Review is skipped when `review_reasons` is empty. Applying decisions is one commit, not one
  immutable version per control.

#### 3. Draft Editor and isolated Preview

```text
+--------------------------------------------------------------------------+
| [1 Application + preparation/draft status]               [2 Settings]    |
|--------------------------------------------------------------------------|
| [3 Workflow landmark]                         [4 Autosave state]          |
|--------------------------------------------------------------------------|
| [5 Editor, about 60%]                    | [6 Preview, about 40%]         |
| Section heading                          | Draft label + refresh state    |
| Claim text [status]                      |                                |
| Linked facts / warnings / blockers       | sandboxed server HTML iframe   |
| Edit | regenerate | remove               | with its own LTR/RTL document  |
| Deterministic fact include/exclude       |                                |
|------------------------------------------|                                |
| Next section / claim                     |                                |
|--------------------------------------------------------------------------|
| [7 Page issues summary]                 [8 Primary: Validate exact draft] |
+--------------------------------------------------------------------------+
```

- Claim status is written in text and exposes its supporting facts; unsupported free text is
  preserved, immediately marked unsafe, and blocks approval rather than save.
- Autosave uses debounce/blur and shows `שומר…`, `נשמר`, or `השמירה נכשלה` without moving
  focus. Regeneration is an explicit Operation.
- A `409` opens a conflict dialog containing `הטקסט שלי` and `הגרסה הנוכחית`, with explicit
  keep-current/reapply choices. It never auto-merges and never overwrites silently.
- Preview is visibly marked `טיוטה`; it does not render a PDF on each edit.

#### 4. Responsive editor fallback

```text
+--------------------------------------+
| [1 Header + compact workflow]        |
|--------------------------------------|
| [2 Status and autosave]              |
| [3 View switch: Editor | Preview]    |
|--------------------------------------|
| [4 One active view at full width]    |
|                                      |
|                                      |
|--------------------------------------|
| [5 Issues]          [6 Primary action]|
+--------------------------------------+
```

- At narrow desktop/tablet widths the two panes become one accessible view switch; Editor is
  the default and switching views does not discard unsaved text.
- At phone widths controls stack, touch targets remain at least 44px high, and the workflow
  landmark becomes a current-step summary. This is a fallback, not a mobile-first redesign.

#### 5. Validation and explicit Approval

```text
+--------------------------------------------------------------------------+
| [1 Validation heading + exact draft version]                              |
| [2 Result: passed/failed, announced]                                      |
| [3 Blockers]                                                              |
|     reason in plain Hebrew -> allowed resolution action                   |
| [4 Warnings]                                                              |
|     non-blocking explanation                                              |
| [5 Validation/provenance summary]                                         |
| [6 Back to edit]                    [7 Revalidate / Continue to approval]  |
+--------------------------------------------------------------------------+

+-------------------------------- Approval dialog --------------------------+
| [1 “Approve this exact version?”]                                         |
| [2 Company, role, draft version, ValidationRun summary]                   |
| [3 Remaining warnings + one general acknowledgement when required]        |
| [4 Cancel]                              [5 Approve immutable revision]     |
+--------------------------------------------------------------------------+
```

- A failed ValidationRun is shown as a completed result, not a crashed request.
- Blockers disable approval and explain the resolution. Warnings remain non-blocking and may
  require one general confirmation.
- Approval is never automatic or implied by validation. The dialog names the exact validated
  version in human terms; technical provenance remains expandable.
- `412 VALIDATION_STALE` returns to the editor/validation context with an explanation and a
  revalidate action; it is not presented as a server outage.

#### 6. Render and Ready

```text
+--------------------------------------------------------------------------+
| [1 Render heading / Operation phase]                                      |
| [2 Approved revision remains approved]                                    |
| [3 Progress, failure explanation, or passing evidence]                    |
| [4 Back to approved summary]                         [5 Retry render]     |
+--------------------------------------------------------------------------+

+--------------------------------------------------------------------------+
| [1 Ready + success summary]                                               |
| [2 Preview]                              | [3 Exact revision summary]     |
| sandboxed approved HTML                  | validation + provenance        |
|                                          | artifact integrity             |
|                                          | newer draft warning if present |
|--------------------------------------------------------------------------|
| [4 Download recruiter PDF]                         [5 Create new draft]   |
+--------------------------------------------------------------------------+
```

- Render failure never visually demotes the immutable revision below Approved. Retry creates
  and polls a new Operation.
- Ready downloads the exact qualified PDF for the displayed ApprovedRevision. No action uses
  an implicit latest artifact.
- `newer_draft_in_progress` is shown without hiding the usable Ready milestone. An older-
  snapshot/analysis Ready revision is labeled historical for the active context while its
  qualification and files remain intact.
- Submission is absent from this screen until M5.

#### 7. Minimal Settings

Settings is a focused dialog or narrow page containing only auto-generation when review is
not required, AI enabled, default execution mode (`ai` or `deterministic`), provider-configured
status without secrets, open-browser preference, and basic UI preferences. It contains no
model picker, provider picker, Workspace paths, secrets, Profile editor, or Knowledge manager.

### A.5 Keyboard, announcements, and failure presentation

- Every form control has a visible Hebrew label; placeholder text is not a label.
- Route changes focus the `h1`; validation summaries receive programmatic focus after submit.
- Dialog focus is trapped and restored to its invoker. Escape cancels only when cancellation
  cannot approve, discard, or overwrite content.
- Autosave, Operation phase, validation completion, and Ready completion use live regions with
  concise messages; polling ticks themselves are silent.
- Problem Details codes map to stable UI treatments. The safe backend detail is shown; raw
  exceptions, local paths, provider payloads, and secrets are never rendered.
- Unsupported edit, ETag conflict, provider failure, `SOURCE_CHANGED`, stale validation, and
  render failure each preserve the user's last safe state and offer only backend-authorized
  next actions.

## B — Frontend foundation

**Stage B is in progress.** The frontend scaffold is closed on user-run typecheck and
production-build evidence accepted on 2026-08-24.

- [x] Create `frontend/` with React, TypeScript, Vite, and Tailwind. It includes a Hebrew RTL
      document, semantic design tokens, a minimal accessible shell, development/production
      scripts, and a locked dependency graph. User-run `npm run typecheck` and
      `npm run build` both passed.
- [x] Add React Router, TanStack Query, React Hook Form, generated OpenAPI type consumption,
      and a small handwritten client. Providers and the root route wrap the existing shell,
      generated schemas are imported from `openapi/types.ts`, and the client handles safe
      Problem Details, ETag, Idempotency-Key, and `Location`. Frontend functions use arrow
      syntax throughout. User-run `npm run typecheck` and `npm run build` both passed.
- [x] Add the RTL shell, semantic design tokens, focus/error boundary, and route skeletons.
      The existing shell hosts nested routes through `Outlet`, navigation moves focus to the
      route heading, the error boundary exposes only safe messages, and skeletons cover the M4
      path through Ready. The visual design remained unchanged. User-run `npm run typecheck`
      and `npm run build` both passed.
- [x] Add Vite proxy development flow and serve the production build from FastAPI.
      Implemented without visual changes: Vite binds a strict `127.0.0.1:5173` and proxies
      `/api` to the default FastAPI endpoint; production receives an explicit `frontend_dist`,
      fails immediately when the build is incomplete, serves contained files and SPA routes,
      and never shadows `/api/v1` or a missing asset. The first backend run reported
      **34 passed, 1 failed**: the architecture guard correctly found a second path-containment
      implementation in `api/frontend.py`. The local predicate was removed in favor of
      Starlette `StaticFiles`; the guard was not weakened and the focused rerun passed
      **35 tests**. User-run `npm run typecheck` and `npm run build` also passed.
- [x] Add the shared UI primitives that express the A.2 visual foundation as components.
      Taken before Operation polling so Stage C screens are not built on ad-hoc classes.
      The theme gained a semantic type scale, an explicit 4px spacing base, control and
      surface radii, an overlay shadow, `cv-border-strong`, `cv-blocker-hover`, and
      `cv-on-accent`. `frontend/src/ui/` holds the primitives derived from the A.4 frames:
      `Button`, `Card`, `PageHeading`, `StatusBadge`, `Callout`, `Field`, `TextInput`/
      `TextArea`, `Select`, `Checkbox`, `LtrText`, `Dialog`, `LiveRegion`, `ActionBar`,
      `SummaryList`, `TechnicalDetails`, `ViewSwitch`, and `WorkflowSteps`. Components read
      tokens only, and none writes its own focus ring: the global `:focus-visible` rule owns
      focus and the guard below refuses `outline-none`. `StatusBadge` and `Callout` make the
      icon and the Hebrew `אזהרה`/`חסימה` label part of the type, so color is never the only
      status signal. `Dialog` is the native `<dialog>` element, which supplies the A.5 focus
      trap, inert background, and focus restoration without a dialog dependency; Escape is
      refused when `dismissible` is false. User-run `npm run typecheck` and `npm run build`
      both passed on the first set of primitives.
- [x] Add a derived design-token guard, `frontend/scripts/check-design-tokens.mjs`, wired
      into `npm run build` as `lint:tokens`. It reads the token names out of the `@theme`
      block in `styles.css` rather than a hand-kept list, so a renamed token fails instead of
      producing a class Tailwind never generates. It refuses literal colors, raw Tailwind
      palette utilities, `outline-none`/`outline-hidden`, and any unknown `cv-` color,
      radius, or shadow token. Its exception list is deliberately empty. The guard was
      proven to fail: a probe component carrying one violation of each rule produced five
      errors and exit 1, and the tree returned to green when the probe was removed.
- [ ] Add shared Operation polling without WebSocket or SSE.
- [ ] **Contract change (Class B): `OperationResponse` reports `is_terminal` and stops
      flattening its closed sets to `str`.** The first draft of the frontend kept its own
      copy of `TERMINAL_OPERATION_STATUSES`, because the HTTP schema typed `status` as a
      plain string. Which statuses end an Operation is a lifecycle rule the application
      layer already owns in `is_terminal_operation`, so the client copy could only go stale.
      `OperationResponse.is_terminal` is a computed field over that same predicate, and
      `operation_type`, `status`, `phase`, and `failure_code` are typed as the application
      enums, so `openapi/types.ts` carries real unions.

      It was first written as an ordinary field supplied by `operation_response`, and the
      non-browser suite failed on
      `test_active_operation_is_projected_as_the_same_operation_representation`: the same
      representation is also built as the `active_operation` of an application projection,
      which does not go through that helper. The test caught the exact class of defect it
      was written for. Making the value computed removed the second place to forget rather
      than adding the field to the second caller. The frontend keys its Hebrew label
      maps by those unions, which turns a new backend status into a failed frontend build
      rather than an untranslated value on screen. `openapi/openapi.json` and
      `openapi/types.ts` were regenerated; the entry-level diff is four `$ref`s replacing
      inline strings, three new enum components, and one added required boolean.
- [ ] Add Vitest, React Testing Library, Playwright Web E2E, and axe foundations without
      blanket DOM snapshots.

## C — Intake, analysis, and review

- [ ] New Application form, local `.txt` read, duplicate precheck/override, and creation.
- [ ] Explicit Analyze action and Operation Progress.
- [ ] No-review continuation using Analyze's explicit initial SelectionPlan ID.
- [ ] Review-reason form and one Apply Decisions commit.
- [ ] Provider failure, retry, deterministic continuation, cancellation, and
      `SOURCE_CHANGED` presentation.

## D — Draft Editor and preview

- [ ] Structured claims/sections, linked facts, warnings, blockers, and deterministic
      selection changes.
- [ ] Debounced/blur autosave with ETag and explicit conflict resolution.
- [ ] Section/claim regeneration Operations and safe failure behavior.
- [ ] Unsupported free text preserved as pending/unlinked and blocked from approval.
- [ ] Isolated server-rendered HTML preview with Hebrew, English, and mixed direction.
- [ ] Desktop split and responsive single-view fallback.

## E — Validate, approve, render, and Ready

- [ ] Validation outcomes, blocker/warning hierarchy, edit/revalidate path.
- [ ] Explicit approval confirmation bound to the exact eligible ValidationRun.
- [ ] Render Operation, failure/retry, and preservation of Approved state.
- [ ] Ready preview, exact PDF download, validation/provenance, and New Draft.
- [ ] Old Ready plus newer draft and historical-context warning presentation.
- [ ] Minimal Settings within the approved safe surface.

## F — M4 gate

- [ ] A real built-Web E2E completes Create through Ready against FastAPI, worker, SQLite,
      filesystem, and renderer without mocking application services or projections.
- [ ] The journey covers review-required and no-review paths.
- [ ] The central failure matrix covers unsupported edit, validation block, stale validation,
      ETag conflict, provider failure, `SOURCE_CHANGED`, render failure/retry, and old Ready
      with newer draft.
- [ ] Chromium full E2E and central WebKit smoke pass.
- [ ] axe passes on New Application, Analysis Review, Draft Editor, Validation, and Ready.
- [ ] The UI explains state, blockers, and safe next actions without requiring technical IDs,
      hashes, paths, logs, or architecture knowledge.

## Current next action

The design system is closed. Add shared Operation polling through TanStack Query without
WebSocket, SSE, synthetic percentages, or automatic mutation retries, rendering it with the
existing primitives. Do not implement Dashboard navigation, tracking endpoints, or the
Stage C intake flow yet.

One A.4 surface is deliberately not a primitive: the sandboxed preview frame. Its direction
isolation and refresh behavior depend on the render contract, so it is built in Stage D with
the screen that owns it rather than guessed at now.
