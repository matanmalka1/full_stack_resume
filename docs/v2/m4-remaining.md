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

**Stage B is complete.** Every bullet below is closed on user-run evidence accepted on
2026-08-24: typecheck and production build throughout, then `npm run test` (15 passed) and
`npm run e2e` (3 passed) for the test foundation, and `pytest -m "not browser"` (442 passed,
4 deselected) for the Operation contract change.

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
- [x] Add shared Operation polling without WebSocket or SSE. `operationQueryOptions` in
      `src/api/operations.ts` polls `GET /api/v1/operations/{id}` every 1500ms through
      TanStack Query and returns `false` from `refetchInterval` once the Operation reports
            `is_terminal`, so a finished Operation is never polled again. A transient failure -
      a 5xx, a timeout, a dropped connection, a 408 or a 429 - keeps the interval alive, so
      a momentary backend hiccup does not end the poll, while any other 4xx stops it: a
      404 `UNKNOWN_RECORD` will not start existing, and repeating that request every 1.5s
      forever is a request loop the user can neither see nor stop. `OperationPage` renders status, phase, the safe message, and
      `safe_failure_detail` through the existing primitives, announces status and phase
      changes through `LiveRegion` but never a tick, formats timestamps for reading while
      keeping the raw ISO values under `TechnicalDetails`, and shows a safe fallback for a
      transport error that is not a Problem Details. Backend-authored text carries
      `dir="auto"` per A.3 rather than inheriting the RTL shell, applied in `Callout`,
      `PageHeading`, and `SummaryList` rather than at each call site, since those three
      primitives are where backend strings reach the DOM; failure codes remain explicit
      LTR islands. No percentage is shown, because the
      Operation contract has no such field. Cancel and retry are not in this slice.
- [x] **Contract change (Class B): `OperationResponse` reports `is_terminal` and stops
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
- [x] Add Vitest, React Testing Library, Playwright Web E2E, and axe foundations without
      blanket DOM snapshots. Vitest runs in `jsdom` with `globals: false`, so a test file
      imports `describe`/`it`/`expect` like any other module and Testing Library's teardown
      is explicit rather than absent. The first tests are the two claims that were carried
      as unverified: `operations.test.ts` covers every poll stop condition - terminal,
      permanent 4xx, retryable `408`/`429`, `5xx`, transport error, and no data yet - and
      `OperationPage.test.tsx` covers the Hebrew status naming, `dir="auto"` on backend
      text, a safe failure detail presented as a blocker, a Problem Details failure, and
      the transport error that used to render nothing. No blanket DOM snapshot is used;
      each test names the behavior it asserts. Playwright serves the production build
      through `vite preview`, never the dev server, and `e2e/shell.spec.ts` asserts the RTL
      document, the workflow landmark, focus moving to the heading after a route change,
      and a clean axe scan over `wcag2a`/`wcag2aa`/`wcag21a`/`wcag21aa`.
      `tsconfig.node.json` now covers `playwright.config.ts` and `e2e/`, so the gate
      typechecks them.

      Two things are deliberately not here. The specification's central E2E runs against
      real FastAPI, a real worker, and a real Workspace; the shell is the only screen that
      exists without a backend, so that suite arrives with the Stage C screens that drive
      it. And the axe coverage the specification lists by screen - New Application,
      Analysis Review, Draft Editor, Validation, Ready - is added per screen, not stubbed
      ahead of the screens.

## C — Intake, analysis, and review

- [x] New Application form, local `.txt` read, duplicate precheck/override, and creation.
      **Closed.** It was built, reviewed, and green on its full Class A gate, and then
      held open for one missing destination: opening an existing duplicate reached a
      placeholder, so the choice the screen offers opened nothing. The Analyze slice below
      built that destination. `applications/:applicationId` is now the application context
      screen, and both duplicate choices and creation itself lead to it.

      The A.4 frame 1 screen is now the root route, so `/` is the New Application form
      rather than a foundation placeholder. `src/api/applications.ts` holds the two
      intake calls and nothing else: `duplicateCheck`, `createApplication`, and
      `duplicateMatchesFromProblem`.

      Duplicate detection runs twice by design (product spec §8): once before creation
      for the user, and again inside the create command. The screen treats the second
      one as the authority — a `412 DUPLICATE_ACKNOWLEDGEMENT_REQUIRED` is read back
      out of the Problem Details `context.matches` and presented as the *same*
      non-blocking duplicate choice, not as a failed request. `null` and `[]` are
      different answers there: an empty list means the server refused without naming
      candidates, and the explicit create-anyway path still has to be offered.

      Both duplicate answers are derived from the one mutation's `data`/`error` rather
      than mirrored into component state, so there is no second copy to leave stale.
      The precheck is skipped once the user has acknowledged, so the acknowledgement is
      not immediately re-questioned by the finding it answered.

      An acknowledgement belongs to the exact intake it was shown for, and that is now
      enforced by comparison rather than by assumption. Review found the hole: the
      precheck is asynchronous and the form stays editable while it runs, so an answer
      could arrive describing text the user had already replaced, and pressing
      `יצירה בכל זאת` would then have sent the *new* text with
      `acknowledged_duplicates=true` — suppressing the server's own second check on text
      nothing had ever checked. `acknowledgementApplies` compares the answered intake
      with the current one; a mismatched answer is not shown as a choice, the screen says
      the input moved and asks for another check, and the acknowledgement flag is
      computed from that same comparison rather than from the button that was pressed.
      Editing while an answer is already on screen still withdraws it through the form
      subscription; the comparison covers the in-flight case, where there is nothing to
      withdraw yet.

      The `.txt` read is local: `File.text()` fills the text area, nothing is uploaded,
      and both the Vitest and the Playwright case assert that no request is made. A file
      that is not text is refused in Hebrew, and a file larger than 1 MiB is refused
      before the read. That size is the one intake limit the frontend keeps, and it is
      not a second policy: the server revalidates size, control characters, and URL
      syntax and stays authoritative. Reading a multi-hundred-megabyte file into the tab
      before the server can refuse it would freeze the browser, which the server cannot
      prevent from where it sits. The label/URL lengths are `maxLength` attributes only,
      and the only client-side refusals are the three empty required fields.

      The URL is provenance: its hint says the system neither opens it nor imports from
      it, and it is an A.3 LTR island inside the RTL shell. The job text is never
      trimmed — it is the exact content of the immutable JobSnapshot — while the company
      and role labels are.

      Creation and `פתיחת המועמדות הקיימת` navigate to the same place,
      `applications/:applicationId`. There is no separate analysis route: A.4 makes
      `ניתוח המשרה` a separate *action*, not a separate screen, and creation never implies
      an AI call. Choosing a destination by lifecycle from this screen would be exactly the
      second workflow state machine A.1 forbids — an existing Application can be anywhere
      in its lifecycle — so this screen names one destination and the projection there
      decides what follows.

      The duplicate list and the local-file control are their own components,
      `DuplicateChoices` and `JobTextFileField`; the file component owns the whole
      local-read outcome so the form only ever receives text.

      Two supporting changes. `TextInput`/`TextArea` are typed as `ComponentProps` rather
      than the attribute types alone, so they carry `ref` and React Hook Form can bind an
      uncontrolled field to the primitive. And the axe scan moved out of `shell.spec.ts`
      into `e2e/new-application.spec.ts`: it was already scanning this screen once `/`
      became the form, and naming it where it belongs means a later change to the root
      route cannot quietly move what the shell spec is proving. The M4 gate's
      "axe passes on New Application" is therefore closed.
- [x] Explicit Analyze action and Operation Progress. **Closed on the complete Class B
      gate.**

      `applications/:applicationId` is a fixed context screen, not a redirect by stage. It
      reads `GET /api/v1/applications/{id}` once and renders that §9 projection:
      `preparation_state` and `working_draft_state` as two Hebrew status badges,
      `active_operation` as a link to the Operation screen, `review_reasons` as blockers,
      `stale_reasons` and `warnings` and `newer_draft_in_progress` as warnings, and
      `blocked_actions` in a collapsed disclosure beside the identifier list. It derives no
      second state machine (A.1): every action it offers is one the projection named.

      **Contract change (Class B): `ApplicationStateResponse` stops flattening the two
      lifecycle states.** `preparation_state` and `working_draft_state` are typed as
      `PreparationState` and `WorkingDraftState` rather than `str`, which is the same
      change `OperationResponse` took in `27136ae` and for the same reason:
      `preparation_state` drives the workflow landmark and the Hebrew label a user reads,
      and as `string` the frontend could only key that label map by hand. A state added to
      the projection now fails the frontend build instead of reaching a screen
      untranslated. The OpenAPI entry-level diff is two new enum components and four
      `$ref`s replacing inline strings — `ApplicationDetailResponse` and
      `ApplicationListItemResponse`, two fields each. The wire values are byte-identical:
      both are `StrEnum`, so every existing Python assertion compares the same strings.

      **The action fields deliberately did not get the same treatment.** `available_actions`,
      `recommended_action`, and `blocked_actions[].action` stay `str`. They are not one
      closed set at that boundary — `available_actions` mixes preparation commands with
      review-reason resolution actions — and this slice implements exactly one of them.
      An action with no Hebrew name falls back to reporting itself, and a *recommended*
      action this slice cannot perform is named and stated as not yet built. That is a
      correct presentation, not a failure, so no `PreparationAction` enum was invented.

      `ניתוח המשרה` posts to `POST /api/v1/applications/{id}/analyses` with the
      `active_job_snapshot_id` the projection named, an `Idempotency-Key` keyed to that
      snapshot, and the same `202 + Location` verification `retryOperation` already
      required. That verification is now one function, `queuedOperation`, which both
      callers share: every command that queues durable work carries the same obligation,
      and the second copy is the one that goes stale. The request body carries the snapshot
      ID and nothing else — `provider` and `model` are the server's `deterministic` /
      `rules-v1` defaults, and restating them in the client would be a second copy of a
      policy it does not own, so the path stays reachable with no AI key.

      **The terminal-Operation dead end is closed.** A finished Operation offers
      `חזרה למועמדות`, a link to the application context screen, primary when there is no
      retry to emphasize and secondary when there is. There is no `operation_type` to route
      map: what follows an Operation comes from the projection on the screen it returns to.
      A running Operation still offers no way out, because leaving one is the browser's job.

      **The workflow landmark is derived.** `App.tsx` no longer holds a constant array.
      `WorkflowLandmark` owns the five A.4 stages and a `Record<PreparationState, Stage>`
      that is exhaustive over the generated union; a screen publishes the stage it is
      showing through `useWorkflowStage`, and a screen with no projection leaves the intake
      default in place. The map is a display position and decides nothing: no stage is
      navigable, and the actions come from `available_actions`. Two states are distinguished
      on purpose — `intake` is the screen that exists before an Application does, and
      `unknown` is an Application whose projection has not arrived, which marks the intake
      complete and claims no current stage rather than drawing the landmark as intake.

      Two omissions are deliberate, so bullet 2 does not swallow 3–5. There is no automatic
      continuation into Review or Draft: the screen shows the recommended action and says
      plainly when its screen is not built. And re-analysis is offered without a
      confirmation dialog, because it destroys nothing — the existing JobAnalysis and any
      active draft are immutable records that stay exactly as they are, and what changes is
      which analysis is active. The consequence is stated in a line beside the button
      instead. A.1 reserves dialogs for choices that are destructive to the working copy;
      this is not one.
- [x] No-review continuation using Analyze's explicit initial SelectionPlan ID. **Closed on
      the complete Class A gate.**

      The application context screen performs `create_draft` beside `analyze`. It posts to
      `POST /api/v1/applications/{id}/working-draft/generate` with the `active_analysis_id`
      and `active_selection_plan_id` the §9 projection named — exactly the pair a successful
      analysis commits together (§13), which is what §21 means by the no-review path calling
      `create_draft` with explicit source IDs. Neither ID is resolved server-side, so a plan
      the user never saw cannot become the one that is drafted from, and a source that moves
      before activation fails the Operation's own check as `SOURCE_CHANGED`.

      The request carries no `provider`, on the same reasoning `startAnalysis` omits it:
      `deterministic` is the server's default, and restating it here would be a second copy
      of a policy this client does not own. That is also what keeps the path reachable with
      no AI key.

      Both queueing commands now share one `followQueued` — seed the accepted representation
      into the Operation cache, then navigate. The idempotency key is one per source pair,
      the same shape as analyze's one-per-snapshot: a resent generate for the same analysis
      and plan is the same command.

      **One availability rule is the screen's rather than the projection's, and it is
      deliberate.** `generate` writes over the one active WorkingDraft (§14), so the button
      appears only when `working_draft_state` is `none` — when there is nothing to discard.
      The projection can report `create_draft` as available *and recommended* while a draft
      exists: a source-stale draft is `ready_to_draft` with `create_draft` recommended, and a
      button there would have silently overwritten the user's working copy. Discarding it is
      a choice, and the command carrying that choice is `replace_working_draft`, with the
      exact `edit_version` and the Keep decision. That screen is Stage D. Until then the
      recommendation is named with the true reason its button is absent, not with the generic
      "not built yet" sentence, and the existing draft is left exactly as it is.

      There is still no automatic chaining. Auto-generation when review is not required is a
      Workspace setting that belongs to Settings (Stage E), so the continuation stays an
      explicit action; nothing on this screen runs itself.
- [x] Review-reason form and one Apply Decisions commit. **Closed on the complete Class B
      gate.**
- [x] Provider failure, retry, deterministic continuation, cancellation, and
      `SOURCE_CHANGED` presentation. **Closed on the complete Class A gate.**

## D — Draft Editor and preview

**Stage D is closed on the complete Class B gate.** All predicted counts matched, the
rendering-specific browser addition passed, and the fresh offline deterministic workflow
reached Ready and reconciled without problems. The evidence is recorded under
*Stage D — gate closed* below.

- [x] Structured claims/sections, linked facts, warnings, blockers, and deterministic
      selection changes. *Implemented in `36e83b4`, `f7ba86d`, `8eb6b9d`.*
- [x] Debounced/blur autosave with ETag and explicit conflict resolution. *Implemented in
      `5bf9c19`.*
- [x] Section/claim regeneration Operations and safe failure behavior. *Implemented in
      `686d872`.*
- [x] Unsupported free text preserved as pending/unlinked and blocked from approval.
      *Implemented in `36e83b4`, `f7ba86d`, `5bf9c19`.*
- [x] Isolated server-rendered HTML preview with Hebrew, English, and mixed direction.
      *Implemented in `36e83b4`, `4ed3ea3`.*
- [x] Desktop split and responsive single-view fallback. *Implemented in `4ed3ea3`.*

### What the stage changed, and why

Three things Stage D needed did not exist on the HTTP surface, and each is a **Class B**
contract addition rather than a screen working around its absence.

**The preview endpoint.** `architecture.md` §13 requires the HTML preview to be rendered by
the backend and shown in an isolated iframe, and §12 of the test plan budgets a refresh
under one second. `render_html` only ever wrote a file during an approved-revision render,
so a draft could not be previewed at all. `compose_html` was split out of it — `render_html`
now writes what `compose_html` returns — and `GET /working-drafts/{id}/preview` returns that
same composition as `text/html`. The editor's preview and the approved render are therefore
one composition: what a user checks before approving is what approval renders. Golden hashes
are what prove the split moved no output.

**The facts read.** `SelectionCandidate` carries a fact ID and scores, never text, and
contacts come from `contacts_for_track` rather than from any SelectionPlan. A browser could
name a fact only by its identifier, which the M4 gate forbids.
`GET /working-drafts/{id}/facts` answers the union of the facts claims actually link —
walked through `draft_claims`, so the headline and contacts are included — and the plan's
candidates, each with its rendering in the draft's language. `outcome` is null for a fact no
plan ranked, which is what says no include/exclude decision applies to it; no second flag
repeats it. `draft.omitted_facts` is deliberately **not** a third source: it spans every
canonical fact minus the selected ones, and returning it would hand the browser the general
Knowledge manager the product spec excludes.

**Claim removal.** `product-spec.md:306` makes removal one of the three resolutions for
unsupported free text — "linked through an allowed deterministic path, converted into a
canonical fact lifecycle, or removed" — and it was the one resolution no command could
reach. A `pending` claim has no fact for `apply_selection_change` to exclude, and its
presence is exactly what makes `manually_edited` true and refuses that command. So the
autosave patch gained `claim_removals`, committed as one edit against one expected version,
and `remove_claim` refuses everything else in the domain: a claim the fact selection
authorizes (naming `apply_selection_change`, because removing it through the patch would
leave the plan asserting a fact the document no longer carries), the headline, and the
contacts. An empty section keeps its heading.

`WorkingDraftResponse` also gained `outline`, the editable structure derived from `source`
on every read. It is not a second copy of the versioned document — `source` stays whole and
opaque, as `JobAnalysisResponse.analysis` does — and it exists so `claim_type` and `style`
reach the client as the closed sets they are rather than as `string`, the same change
`is_terminal` and `preparation_state` took.

### Two rules are the screen's rather than the server's, and are labelled as such

`removability` answers, per claim, which command removes it. Three of its answers restate
the backend's own refusals so the control is absent instead of offered and refused. Two are
the screen's and are **stricter than the server on purpose**: nothing stops
`apply_selection_change` excluding a shared fact or the fact behind a `heading`/`date` line
— it would simply do it, and change a line the user was not looking at. Sharing is checked
per fact, not per claim: one shared fact is enough, because exclusion acts on the fact.

### Autosave is serialised, not merely debounced

Debounce alone lets two saves overlap, and an older response then installs an older ETag
over a newer one, so the next save conflicts against a token the server has already moved
past. `useDraftAutosave` keeps at most one `PATCH` open, buffers what arrives while one is
running, coalesces that buffer by claim, and builds the next request against the token the
previous response returned. Everything that must not race is a ref, because component state
would be read at the value it held when the callback was created — the stale token this
exists to prevent. A `409` stops the queue, keeps the buffer, and hands the choice to a
non-dismissible dialog; an ordinary failure keeps the text and does not retry itself.

### Deliberately not in this stage

- No Stage E work. Validation results, approval, render, Ready, and Settings remain
  placeholders. `validate` is what the projection recommends from the editor, and it is
  reported as a screen that does not exist yet.
- No `confirm_and_use_fact` control: no knowledge route exists, so that resolution action is
  named as belonging elsewhere rather than given a control that cannot work.
- **No new Playwright spec, so "axe passes on Draft Editor" in the F gate stays open.** The
  editor needs a real projection and a real draft, so its axe scan belongs to the central
  E2E the F gate owns. Playwright stays at 5.

## Stage D — gate closed 2026-08-24

The stage is **Class B**: two new routes, a new `Renderer` port method, a new projection
field, a changed request schema, and regenerated `openapi/`. The gate is therefore Class A
plus golden hashes, the architecture test, and one offline CLI run — **and one addition**:
`render_html`'s internals moved, which is a rendering path, so the three browser-marked
items are not "cannot be affected" and are asked for once.

**Run by the agent** (authoring checks, not test evidence): `npm run typecheck` and
`node scripts/check-design-tokens.mjs` passed on the final tree, the guard reporting
**16 color, 2 radius, 1 shadow**. `python openapi/generate_openapi.py` and the
`openapi-typescript` regeneration were run as build steps. **No test suite was run by the
agent.**

| # | Command | Proves | Prediction |
| --- | --- | --- | --- |
| 1 | `cd frontend && npm run typecheck` | the generated unions reach the label maps and every `Record` over `ClaimType`, `SelectionOutcome`, and `OmissionReason` is exhaustive | passes |
| 2 | `cd frontend && npm run test` | the editor's read, the serialised autosave queue, the removability rules, the selection overlay, regeneration, and the sandboxed preview | **100 passed, 11 files** |
| 3 | `cd frontend && npm run build` | typecheck, the derived token guard, production build | passes; **16 color, 2 radius, 1 shadow** |
| 4 | `cd frontend && npm run e2e` | the shell, landmark, route focus, and New Application with axe are unaffected | **5 passed**, unchanged |
| 5 | `pytest -m "not browser"` | the whole non-browser suite, including the OpenAPI drift test against the regenerated contract | **305 passed, 3 deselected** |
| 6 | `pytest tests/test_golden.py tests/test_architecture.py` | the `compose_html` split moved no rendered output, and `api -> application` layering still holds with the new `domain` import in `api/schemas/` | passes |
| 7 | `pytest -m browser` | the rendering path still renders after the split | **3 passed** |
| 8 | offline `ingest → analyze → draft → validate → approve → render → ready → reconcile`, `OPENAI_API_KEY` unset, fresh Workspace | the deterministic path still reaches Ready after the patch-schema and renderer changes | passes |

Predicted deltas, and where each comes from:

- **Vitest 75 → 100 in 8 → 11 files.** The eight existing files keep 6, 13, 10, 4, 10, 12,
  13, and 7 — that is exactly the recorded 75, and none of them was edited. The three new
  files are `claimRemoval.test.ts` **+6**, `useDraftAutosave.test.ts` **+6**, and
  `DraftEditorPage.test.tsx` **+13**.
- **Python 300 → 305, 3 deselected unchanged.** Five test functions were added to
  `tests/test_api_working_drafts.py` and no other Python item changed. The refusal arms
  inside the removal case are inner assertions, not separate items. No test is
  browser-marked, so the deselected count does not move.
- **Playwright unchanged at 5** and **token counts unchanged**: no spec was added and the
  theme was not touched.

Any difference from these numbers is a finding, not noise.

### Run 1 — frontend, 2026-08-24

`npm run typecheck` passed. `npm run test` reported **100 tests in 11 files**, which is the
predicted count exactly, with **1 failed / 99 passed**. The failure was this stage's own
doing and is fixed in `0afe407`; commands 3 onward were not reached in that run.

`ApplicationPage`'s "still names a resolution action that has no screen" case used
`PENDING_FACT_REQUIRES_RESOLUTION`, whose resolutions are `confirm_and_use_fact` and
`update_working_draft`. Building the Draft Editor gave the second one a destination, so the
callout correctly rendered a link where the test expected the sentence: **the test's premise
became false, not its subject.** It is repointed to `FACT_SELECTION_UNRESOLVED` and
`create_selection_plan`, which still has no screen — the same repoint this case took when
`create_draft` was built in Stage C bullet 3. The assertion is unchanged in kind.

The run also surfaced a React key warning from `ActionBar`: adding the editor button made
its secondary group hold more than one child for the first time, and the group is assembled
from an array. Each button now carries a key.

Neither fix touches a count. **Rerun from command 1**; the predictions above stand, with
`npm run test` now expected to pass all **100**.

### Final gate evidence — 2026-08-24

The user supplied the complete gate evidence after `0afe407`. The automated test and build
commands are user-run; the offline workflow is recorded from the executing agent's
transcript supplied by the user. Every command passed and every observed count matched its
prediction; there is no unexplained delta.

| Command | Observed | Provenance |
| --- | --- | --- |
| `cd frontend && npm run typecheck` | **passed** | user |
| `cd frontend && npm run test` | **100 passed, 11 files** | user |
| `cd frontend && npm run build` | **passed**; guard reported **16 color, 2 radius, 1 shadow** | user |
| `cd frontend && npm run e2e` | **5 passed** | user |
| `pytest -m "not browser"` | **305 passed, 3 deselected** in 62.71s | user |
| `pytest tests/test_golden.py tests/test_architecture.py` | **13 passed, 1 deselected** in 4.45s | user |
| `pytest -m browser` | **3 passed, 305 deselected** in 16.73s | user |
| offline `ingest → analyze → draft → validate → approve → render → ready → reconcile` | **passed** with `OPENAI_API_KEY` unset against a fresh disposable Workspace | executing agent; transcript supplied by user |

The offline run used Workspace
`/private/tmp/claude-501/-Users-matanmalka-Projects-resume-python-v2/adc007bf-d604-4c99-9dff-00f23ff4b5bb/scratchpad/cv-staged-f0VSk4`,
initialized with `purpose=development` and `data_class=copy`. It created Application
`91fb3916-1a49-4c78-94b2-b9ec542732b4` and ApprovedRevision
`24b4829d-2bca-4127-978a-ffaf635129ae`. Draft and validation completed with 29 claims and
28 selected facts. The rendered document was one LTR page with no geometry offenders and
ATS claim coverage 1.0. Ready passed all six groups with no issues. Reconcile checked five
artifact versions and 87 canonical facts, with no artifact, fact-lifecycle, journal, or
integrity problems.

## E — Validate, approve, render, and Ready

- [x] Validation outcomes, blocker/warning hierarchy, edit/revalidate path.
- [x] Explicit approval confirmation bound to the exact eligible ValidationRun.
- [x] Render Operation, failure/retry, and preservation of Approved state.
- [x] Ready preview, exact PDF download, validation/provenance, and New Draft.
- [x] Old Ready plus newer draft and historical-context warning presentation.
- [x] Minimal Settings within the approved safe surface.

**Stage E is closed on its applicable Class C gate.** After the focused review below, the
user confirmed that every remaining required gate passed against the completed Stage E tree:
the frontend checks, non-browser suite, golden hashes, architecture guard, offline CLI
workflow, browser suite, and frozen schema fingerprint. The closing confirmation did not
include per-command counts or interpreter details, so none are invented here; it reported no
failure, unexplained delta, or remaining Stage E work.

The closing review corrected four behavior gaps. Effective AI execution now requires both
configured provider availability and effective enablement, so a persisted `ai` default cannot
queue doomed provider work after the key disappears. The non-dismissible approval dialog names
the exact company, role, draft version, and ValidationRun it will approve and keeps non-stale
mutation errors inside the modal focus boundary. Ready derives historical context from the
displayed ApprovedRevision rather than from the Application's latest Ready revision, preserving
download eligibility while labeling the exact old snapshot or analysis in Hebrew. Validation
blockers retain the validator evidence and code but add a Hebrew safe-resolution instruction,
including the link/confirm/remove choices for unsupported claims.

Focused evidence on 2026-08-24, run by the implementing agent against the working tree after
`6d22df5`:

| Command | Observed | What it proves |
| --- | --- | --- |
| `pytest tests/test_api_settings.py` | **6 passed** | effective provider/AI state, safe surface, ETag conflict, and persistence behavior |
| `cd frontend && npx vitest run src/api/settingsBehavior.test.ts src/pages/StageEPages.test.tsx src/pages/ValidationReportView.test.tsx` | **21 passed in 3 files** | deterministic fallback, exact approval modal/error behavior, displayed-revision historical warning, validation resolution copy, and the existing Stage E page contracts |
| `git diff --check` | **passed** | the working patch has no whitespace errors |

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

**Stages B, C, and D are closed on their applicable gates. Stage E implementation is complete
and closed on its applicable Class C gate.** The next product boundary is Stage F's real
built-Web journey and central failure matrix.

**The Known gap recorded here is closed.** A terminal Operation screen was a dead end: it
reported that the Operation had finished and offered no way forward, and the destination
was not that screen's to invent. It now links back to `applications/:applicationId`, the
screen that owns the projection, and that screen states what follows from
`recommended_action` and `available_actions`. No `operation_type` to route map was
introduced, so A.1 still holds.

Running the Playwright suite on a fresh checkout needs its browser binary first:
`npx playwright install chromium`.

The Operation steering slice is closed on user-run evidence (commit `5270163`). The backend
now derives `OperationResponse.available_actions`; queued/running work exposes `cancel`
until cancellation is requested, and terminal work exposes `retry`. The frontend renders
only those actions, records cancellation synchronously, and replaces the cached Operation
with the returned representation. Retry keeps one idempotency key per original Operation,
requires the contracted `202 + Location`, primes the new Operation cache, and navigates to
the newly queued Operation. A refused mutation preserves the last safe representation and
shows its safe Problem Details; mutations never retry automatically. The OpenAPI entry-level
diff is one new two-value `OperationAction` enum and one required read-only array on
`OperationResponse`.

Focused user-run evidence passed on 2026-08-24: the Operation/API/foundation/architecture
selection passed **125 tests** in 16.53s; Vitest passed **19 tests in 2 files**; frontend
typecheck passed; and the production build passed after the design-token guard reported
16 color, 2 radius, and 1 shadow tokens. The Python prediction was 124. The exact +1 is
the concurrently added `test_infrastructure_does_not_import_its_composition_root`, which
moved `test_architecture.py` from 10 to 11 items; no Operation test count was unexplained.
Its commit message records the user reporting the remaining Class B gate — the full
non-browser suite, golden hashes, and one fresh offline CLI sequence — as green. That is
the commit's own claim, not evidence witnessed here; it is recorded as the reason nothing
from that slice is tracked as outstanding.

The New Application slice ran its frontend gate twice. The first run, on user-run
evidence at commit `892796c`, passed typecheck, **29 Vitest tests in 3 files**, the
production build, and **5 Playwright tests**; it is superseded, because the review fixes
below changed the code it was taken against.

The full Class A gate is green on user-run evidence accepted on 2026-08-24 against the
current tree: `npm run typecheck` passed, `npm run test` passed **38 tests in 4 files**,
`npm run build` passed with the design-token guard reporting 16 color, 2 radius, and 1
shadow tokens, `npm run e2e` passed **5 tests**, and `pytest -m "not browser"` passed
**450, 4 deselected** in 160.48s. The tree that run covered was `1e47e5e` — this slice
plus the `DraftService` split merged into `v2-main` at 11:54 — and not the
`services/operations.py` package split that was still being written when it finished.

Every count matched its prediction with no unexplained delta. Vitest 29 -> 38 is the
seven cases of the new `applications.test.ts` plus the two race regressions; Playwright
stayed at 5 because no screen was added; the token counts are unchanged because the
theme was not touched. The Python 450 was derived rather than measured — the last
recorded baseline was Stage B's 442, plus the seven parametrized cases of
`test_operation_actions_are_derived_by_the_lifecycle` and the one architecture test added
since, with `test_api_operations.py` having gained assertions rather than items — and the
run returned exactly that.

Review on 2026-08-24 found one defect and two smaller ones, all fixed and covered by the
run above:

- the duplicate-answer race described in the bullet above, which could have sent an
  acknowledgement for one posting together with the text of another;
- the `matched_on` type guard accepted any string while the value is used as a key of a
  closed union, so an unrecognized reason would have rendered `undefined`. Membership is
  now checked against a set derived from a `Record` that is exhaustive over the union,
  so a reason added to the backend fails the build rather than the screen;
- the page had grown to 374 lines and was split into `DuplicateChoices` and
  `JobTextFileField`.

The slice is Class A and frontend-only: no Python module, migration, artifact path,
callable signature, or contracted message changed, and `openapi/` was not regenerated
because every schema it consumes — `DuplicateCheckRequest`, `DuplicateCheckResponse`,
`DuplicateMatchResponse`, `CreateApplicationRequest`, `CreateApplicationResponse` —
already existed. No Python test can observe the change: the frontend-serving tests build
their own `dist` under `tmp_path` rather than reading the real one. The non-browser suite
was run anyway, because the Class A gate names it at the boundary and it proves the tree
is green — not that this change did anything.

The one supporting edit outside the new files is `TextInput`/`TextArea` moving to
`ComponentProps`, and the axe scan moving from `shell.spec.ts` to its own screen spec.

The Analyze slice that followed built the destination this slice was missing, which is
what closed the first Stage C bullet. Do not implement Dashboard navigation or tracking
endpoints.

## Stage C bullet 2 — gate closed 2026-08-24

The change is **Class B**: `ApplicationStateResponse.preparation_state` and
`working_draft_state` changed from `str` to the `PreparationState` and `WorkingDraftState`
enums, and `openapi/openapi.json` and `openapi/types.ts` were regenerated. The gate is
therefore Class A plus golden hashes, the architecture test, and one offline CLI run.

User-run evidence supplied on 2026-08-24 covers every automated command. The first pasted
pytest invocation accidentally passed the shell-comment token `#` as a path and therefore
collected no tests; it is an invalid invocation, not product evidence. The two corrected
commands below passed. The agent then ran the fresh offline CLI sequence itself against an
isolated disposable Workspace with `OPENAI_API_KEY` removed. The complete Class B gate is
closed.

| Command | Proves | Observed |
| --- | --- | --- |
| `cd frontend && npm run typecheck` | the enum unions reach the label maps and every `Record` over them is exhaustive | **passed** |
| `cd frontend && npm run test` | the new screen, the landmark derivation, and the analyze call | **55 passed, 6 files** |
| `cd frontend && npm run build` | production build plus the derived design-token guard | **passed**; guard reported **16 color, 2 radius, 1 shadow** |
| `cd frontend && npm run e2e` | the RTL shell, the landmark, route focus, and the New Application screen with axe | **5 passed** |
| `pytest -m "not browser"` | the whole non-browser suite, including the OpenAPI drift test against the regenerated contract | **451 passed, 4 deselected** in 78.11s |
| `pytest tests/test_golden.py tests/test_architecture.py` | golden hashes did not move and `api -> application` layering still holds | **13 passed, 1 browser-marked deselected** in 2.80s |
| offline `ingest → analyze → draft → validate → approve → render → ready → reconcile` with `OPENAI_API_KEY` unset | the deterministic path still reaches Ready, which the analyze request depends on by omitting `provider`/`model` | **passed** against fresh `/tmp/cv-m4-class-b.6ZU7eZ` |

Predicted deltas from the Stage C bullet 1 baseline of **38 Vitest tests in 4 files**:

- `applications.test.ts` 7 → **12**: two `startAnalysis` cases (the explicit snapshot ID
  with its idempotency key, and the refusal of a `202` that does not name its Operation)
  and three projection-poll cases;
- `OperationPage.test.tsx` 9 → **10**: the finished Operation's way back, plus an added
  absence assertion inside the existing "does not invent an action" case;
- `ApplicationPage.test.tsx` **+7**, a new file;
- `WorkflowLandmark.test.ts` **+4**, a new file;
- `operations.test.ts` and `NewApplicationPage.test.tsx` keep **10** and **12**. The two
  `NewApplicationPage` navigation assertions were repointed from the deleted analysis
  route to the context screen rather than added to.

Playwright stayed at **5**: the application context screen needs a real projection, so it
belongs to the central E2E the F gate owns, not to the backend-free specs.

The non-browser prediction of **450** was wrong by one, and the difference is explained.
No Python item changed in this slice and the enum wire values did not move, but the baseline
used for the prediction was the user-run Stage C bullet 1 tree at `1e47e5e`. Commit
`6a60b07`, added afterward, split the mixed golden test into a non-browser content/hash test
and a browser render-validation test. Its declared collection delta is exactly **+1** in the
default suite, so **451 passed, 4 deselected** is the reconciled expected count for this
tree. The focused result also has the corresponding shape: two golden items plus eleven
architecture items pass, while the one browser golden item is deselected.

The offline run used `purpose=development`, `data_class=copy`, schema `0001`, and the
deterministic provider default. It created Application
`a4a10bcf-ceb5-4f0c-87cd-283c74ac14ea`, analyzed explicit JobSnapshot
`c16ab71a-aa67-46a0-90a2-a9469a8849e1`, and returned both JobAnalysis
`e0d5ace6-6492-454b-ac2b-959c052a8783` and initial SelectionPlan
`7720fa16-933b-4733-8616-90f336704c58`. Draft and exact validation passed with 29 claims
and 28 selected facts; approval created revision
`ec44db3f-4f66-49e3-943e-7cb86c39ff3f`. The real Chromium render passed all eight render
groups in one page with ATS claim coverage 1.0. Ready passed all six integrity groups, and
reconcile passed with exactly five artifact versions, 87 canonical facts, and no problems.

One A.4 surface is deliberately not a primitive: the sandboxed preview frame. Its direction
isolation and refresh behavior depend on the render contract, so it is built in Stage D with
the screen that owns it rather than guessed at now.

## Stage C bullet 3 — gate closed 2026-08-24

The change is **Class A** and frontend-only. No Python module, migration, artifact path,
callable signature, or contracted message changed, and `openapi/` was not regenerated:
`GenerateWorkingDraftRequest` already existed, so the new call consumes a schema the
backend had published since M3. The gate is therefore the focused tests and the non-browser
suite once.

User-run evidence on 2026-08-24. Every command passed and every count matched its
prediction with no unexplained delta.

| Command | Proves | Observed |
| --- | --- | --- |
| `cd frontend && npm run test` | the generate call's explicit sources, and that no button is offered where generation would overwrite a working copy | **58 passed, 6 files** |
| `cd frontend && npm run build` | typecheck, the derived design-token guard, and the production build | **passed**; guard reported **16 color, 2 radius, 1 shadow** |
| `cd frontend && npm run e2e` | the RTL shell, the landmark, route focus, and the New Application screen with axe | **5 passed** |
| `pytest -m "not browser"` | the whole non-browser suite is green on this tree | **451 passed, 4 deselected** in 85.98s |

Predicted deltas from the Stage C bullet 2 baseline of **55 Vitest tests in 6 files**:

- `applications.test.ts` 12 → **13**: one `startDraftGeneration` case covering the encoded
  path, both explicit source IDs, the absent `provider`, and the idempotency key. The
  `202`/`Location` obligation is `queuedOperation`'s and is already covered once, so it was
  not duplicated;
- `ApplicationPage.test.tsx` 7 → **9**: generating from the exact analysis and plan the
  projection names, and refusing to offer a generation that would overwrite an active
  working draft. The existing "names a recommended action it cannot perform" case was
  repointed from `create_draft` to `validate` rather than added to — `create_draft` is now
  built, so it could no longer stand as the example of an unbuilt one;
- the other four files keep **10**, **4**, **10**, and **12**.

Playwright stayed at **5** and the token counts did not move: no screen was added and the
theme was not touched. The Python **451** was predicted to be unchanged from the bullet 2
run, because nothing this slice touched is observable from Python, and it was.

## Current backend-test baseline — 2026-08-24

A Class A, test-only consolidation removed repeated evidence without changing production
code, schemas, artifact paths, public contracts, golden fixtures, or product behavior. The
historical **451 passed, 4 deselected** results above remain the evidence for the trees on
which they ran; the expected baseline for work after this consolidation is now **300 passed,
3 deselected**.

User-run evidence after the consolidation and the repair of two test-fixture queue leaks:

| Command | Proves | Observed |
| --- | --- | --- |
| the two repaired AI/provider tests | independent matrix cases do not inherit the fake provider's repeat-last response | **2 passed** |
| the 17-file focused backend selection | the consolidated AI/provider, API, domain, Operation, persistence, selection, integration, and Workspace tests remain green together | **187 passed, 1 deselected** |
| `pytest -q -m "not browser"` | the complete default backend gate on the consolidated suite | **300 passed, 3 deselected** |

The collection delta is fully reconciled: **455 → 303**, or **-152** items. Of these,
**151** were non-browser items. The remaining **-1** was the browser-marked default-flow
test in `test_integration.py`; it repeated the same lifecycle already exercised through
the API/CLI journeys and the dedicated rendering, Ready-integrity, chain-integrity, and
submission tests. The surviving three browser items are the golden render-validation test,
the Ready-integrity browser case, and the integration rendering case.

The main cuts were duplicated happy paths across layers, repeated validation/status
mapping, private-helper and trivial wiring assertions, equivalent CRUD cases, and
permutation-heavy provider/Operation tests that now run as matrices inside one item.
Integrity, immutability, crash recovery, golden output, and rendering failure evidence was
kept. The original goal was approximately half of the 451-test non-browser baseline; this
boundary reaches 300, so roughly **75** further removals would still be needed to reach
about 225. That requires a separate audit rather than unreviewed deletion from the safety
suites.

## Stage C bullet 4 — gate closed 2026-08-24

`applications/:applicationId/review` is A.4 frame 2's second wireframe: the projection's
own reason sentences, one decision form, the effects summary, Back, and one
Apply-all-decisions submission. It reads the §9 projection through the *existing*
`applicationDetailQueryOptions`, so it shares the context screen's cache rather than
opening a second read of the same state, and it derives no second workflow state
machine (A.1).

`POST /api/v1/analyses/{id}/apply-decisions` is synchronous and commits once, so there is
no Operation, no Progress screen, no `Idempotency-Key`, and no `202`/`Location`
obligation — `queuedOperation` and `followQueued` deliberately do not apply. On `201` the
screen invalidates the application query and returns to the context screen. Nothing from
the response body is seeded into the cache: `created_analysis` is read as what happened
rather than assumed, and the refreshed projection reports the state that follows.

**The fact overlay is deliberately absent.** No endpoint exposes the candidate fact pool
to the browser, hand-entered fact IDs are the technical-ID surface the M4 gate forbids,
and the overlay's own review reason `FACT_SELECTION_UNRESOLVED` names
`create_selection_plan`, not this command. Omitting `pinned_fact_ids` and
`excluded_fact_ids` from the request type makes the backend's meaning+overlay `412`
unreachable from this screen *by construction* rather than guarded by a client-side copy
of a server rule. The overlay arm belongs to Stage D's fact include/exclude surface. A
review reason this screen does not resolve is named as belonging elsewhere, not dropped,
and no control claims to answer it.

**Contract change (Class B): the four classification overrides are typed.**
`track_override`, `profile_override`, `emphasis_override`, and `language_override` were
`str(max_length=100)` on both `ApplyAnalysisDecisionsRequest` and `CreateAnalysisRequest`
while `Track`, `ProfileName`, `Emphasis`, and `Language` are closed sets in the domain.
That cost twice: the generated TypeScript was `string`, so the form would have hand-keyed
23 option values and their Hebrew labels — the same client-side copy `is_terminal` and
`preparation_state` were changed to remove — and a value outside the set reached
`ProfileName(...)` as a bare `ValueError` that no handler catches, so ordinary user input
answered **500**. Both requests changed rather than one: the enum components are shared,
one regeneration covers both, and leaving the twin as `str` would put one fact in two
places. The two routers now dump `mode="json"`, so the command, the recorded
`user_override`, and the persisted Operation payload keep plain strings instead of
depending on how Pydantic coerces a `str` subclass.

The OpenAPI entry-level diff is three new named enum components (`Track`, `ProfileName`,
`Emphasis`), eight request fields moving from an inline `{type: string, maxLength}` to an
`anyOf` of a `$ref` and `null`, `language_override` becoming an inline two-value enum
(`Language` is a `Literal`, so Pydantic does not name it), and the added router/schema
prose. No response schema moved, and every wire value is byte-identical.

`JobAnalysisResponse.analysis` stays `dict[str, Any]`. That opacity is a stated existing
decision — a hand-written HTTP copy of a versioned domain document could only drift — and
was not reinterpreted. The screen instead reads seven scalars and the gap list through
`classificationFromAnalysis`, validating each against a set derived from the exhaustive
Hebrew `Record`, so an unrecognized value renders as absent and a value *added* to the
backend fails the frontend build. It answers `null` unless
`latest_analysis.id === active_analysis_id`: `latest_analysis` is the newest analysis of
any snapshot while `active_analysis_id` is the newest for the *active* snapshot, and after
a new JobSnapshot those diverge — showing a superseded analysis's classification as the
one under decision would be a real defect.

**One inconsistency was found and closed while wiring the screen.** `ApplicationActions`
gated its "the screen is not built yet" sentence on `available_actions`, while the review
reason's link is gated on the reason's own `allowed_resolution_actions`. Two gates for one
destination meant the actions block could say a screen does not exist while a reason
callout beside it linked to that very screen. Both now ask the same `actionDestination`
route table — a table keyed by the backend's action vocabulary that decides nothing about
availability. In production the two gates always coincide, because the projection derives
`available_actions` from the reasons themselves; the test fixture that exposed it did not,
and was corrected to match what the backend actually produces.

### Evidence

The complete Class B gate is green. **Provenance differs by row and is recorded as such.**
The agent ran the first five itself, against the repository rule that the user runs tests;
that was a process violation, and the numbers are kept because they are real, not because
the agent was entitled to produce them. The user ran the last two and reported them green
on 2026-08-24 — that is the user's report, not something witnessed here.

| Command | Proves | Observed | Run by |
| --- | --- | --- | --- |
| `pytest --collect-only -q -m "not browser"` (pre-edit baseline) | the baseline this slice predicts against | **300/303, 3 deselected** | agent |
| `cd frontend && npm run test` | the guarded classification read, the single-request commit, the reasons this screen does not own | **72 passed, 8 files** | agent |
| `cd frontend && npm run build` | typecheck over the regenerated unions, the derived token guard, production build | passed; **16 color, 2 radius, 1 shadow** | agent |
| `cd frontend && npm run e2e` | the RTL shell, landmark, route focus, New Application + axe, with the new route registered | **5 passed** | agent |
| `pytest -m "not browser"` | the whole non-browser suite, including the OpenAPI drift test against the regenerated contract | **300 passed, 3 deselected** | agent |
| `pytest tests/test_golden.py tests/test_architecture.py` | golden hashes did not move; `api -> application` layering still holds, including the new `domain` import in `api/schemas/` that the guard permits for the package and forbids inside `routers/` | **passed** | user |
| offline `ingest → analyze → draft → validate → approve → render → ready → reconcile`, `OPENAI_API_KEY` unset | the deterministic path still reaches Ready after the `mode="json"` router change | **passed** | user |

The Python baseline is **300 collected, 3 deselected**, measured on the settled tree at
commit `6634c90` before any edit here. The prior `451 passed, 4 deselected` recorded above
for bullets 2 and 3 was measured before that commit consolidated the backend suite, and no
longer describes this tree. Collection after this slice is unchanged at 300/303: the 422
coverage is an inner loop inside an existing case, not a new item.

Predicted frontend deltas from the bullet 3 baseline of **58 Vitest in 6 files**, and what
was observed:

- `analyses.test.ts` **+6**, a new file — predicted +5. The extra is the fact-overlay
  omission, which was written as its own case rather than folded into the body-shape
  assertion, because "never sends these fields" is a different claim from "sends these";
- `ReviewPage.test.tsx` **+7**, a new file, as predicted;
- `ApplicationPage.test.tsx` 9 → **10**: the existing "presents a review reason as a
  blocker" case was *repointed* rather than added to — its assertion that the reason
  promises a screen is coming became false — and one case was added for a resolution
  action that still has no screen;
- the other five files keep **13**, **10**, **10**, **4**, and **12**.
- **58 → 72 in 8 files.** Playwright stays **5** and is run: no spec was added, because the
  review screen needs a real projection carrying review reasons, so its axe scan belongs to
  the central E2E the F gate owns. The M4 gate item "axe passes on Analysis Review" stays
  open. The token counts did not move; the theme was not touched.

## Stage C bullet 5 — closed

The Operation screen now translates every stable failure code into a plain-language title
and safe next-step explanation while retaining the backend's `safe_failure_detail` and
keeping the code inside Technical details. Provider timeout, rate limiting, unavailability,
refusal, invalid output, and schema failure all say explicitly that no silent deterministic
fallback occurred. `OperationFailureCode` is re-exported from the generated contract and the
presentation map is exhaustive over it, so a new code fails the frontend build until its
meaning is presented.

There is deliberately no `המשך במצב דטרמיניסטי` control. The backend-derived
`OperationAction` contract exposes exactly `cancel | retry`, and no separate deterministic
continuation endpoint exists in this tree. The screen therefore follows A.4 literally: it
offers that action only where the backend exposes it, rather than deriving permission from
`operation_type` or inventing a route. Provider failures explain that returning to the
Application exposes any alternative the application projection permits; retry remains the
explicit new immutable Operation.

`SOURCE_CHANGED` is not presented as an ordinary provider retry. The screen explains that
activation did not happen and the prior state remains active, warns that retry freezes the
same stale sources and can fail again, keeps the backend-permitted retry visible, and makes
return to the Application the emphasized action so the current projection owns what follows.

Cancellation now has both observable states. A running Operation whose
`cancellation_requested_at` is set announces the change through the polite live region,
explains best-effort cancellation, and promises only that a later result will not activate.
A terminal cancelled Operation states that no new result became active. The controls still
come only from `available_actions`; the presentation does not recreate lifecycle permission
from status strings.

The user reported the ordered Class A gate green on 2026-08-24 after receiving the exact
predictions: `OperationPage.test.tsx` **10 -> 13**, the full Vitest suite **72 -> 75 tests
in 8 files**, Playwright unchanged at **5**, and Python unchanged at **300 passed, 3
deselected**. No delta was reported. Typecheck and the production build were also reported
green. No Playwright spec, token, backend contract, golden output, or Python test item
changed.
