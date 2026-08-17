# Local-First CV Workspace v2.0 Product Specification

Status: **Draft for review**

Product version: **2.0**

Base v1 revision: **`v1.0.0` / `2cc31c7`**

Primary specification language: English

Primary UI language: Hebrew

Official target platform: macOS

## תקציר מנהלים

v2.0 הופך את מנוע ה-CLI המאומת של v1 ל-Workspace מקומי מלא למועמד יחיד.
המערכת כוללת FastAPI מקומי, ממשק React בעברית, SQLite ל-state מובנה
ו-filesystem ל-snapshots ולתוצרים immutable. ה-CLI וה-Web אינם קוראים זה לזה;
שניהם clients של אותה שכבת application.

הזרימה המרכזית היא:

`Create -> Analyze -> Review if required -> Draft -> Edit -> Validate -> Approve -> Render -> Ready`

Review הוא שער מבוסס חריגים, לא מסך חובה. המערכת ממשיכה אוטומטית ל-draft כאשר
אין ambiguity מהותית, gap הדורש החלטה, claim לא נתמך או בחירת עובדות לא פתורה.
האישור ב-Web תמיד מפורש. WorkingDraft הוא המסמך היחיד שניתן לשינוי;
ApprovedRevision וכל התוצרים הנגזרים ממנה הם immutable.

AI מסווג ומציע ניסוח תחת חוזים מובנים. הוא אינו מקור אמת ואינו יוצר ישויות domain
ישירות. עובדות canonical, policy דטרמיניסטי ו-validation נשארים סמכותיים. מסלול
דטרמיניסטי מלא עד Ready PDF ממשיך לעבוד ללא API key.

הפיתוח מתבצע ב-branch `v2-main` וב-worktree המבודד `../resume_python-v2`.
פיתוח ומיגרציה משתמשים בעותקים בלבד. אין dual-write, ואין גישה ל-workspace החי של
v1 עד cutover מפורש לאחר Release Ready מלא.

## 1. Authority and interpretation

For v2.0, authority is ordered as follows:

1. This product specification defines binding product semantics, scope, safety, and
   observable behavior after it is approved.
2. `docs/v2-state-and-use-cases.md` defines the detailed state, command, query, and
   permission contracts consistent with this specification.
3. `docs/v2-architecture.md` defines the technical architecture that implements those
   contracts.
4. The implementation, test, and migration plans define execution and evidence.
5. `docs/v1-upgrade-handoff.md` and v1 behavior remain binding evidence for every v1
   safety or factual invariant that this specification does not explicitly replace.
6. Legacy code and data are current-state evidence, not permission to weaken a v2
   contract.

Normative terms such as **must**, **must not**, **should**, and **may** are intentional.
An internal naming or packaging decision may change without approval when observable
behavior and every invariant remain unchanged. A semantic change, scope expansion,
migration risk, or weakened factual boundary requires an explicit decision.

The repository's current agent instructions still describe v1 and prohibit the Web UI
as out of v1. They must be updated through an explicit authority handoff after these v2
documents are approved and before M1 implementation begins. This draft does not
silently override those instructions.

## 2. Product goal

> A single candidate can create a job application, analyze the job, resolve only the
> decisions that require human judgment, produce and edit a fact-linked CV, validate and
> explicitly approve one exact revision, render a valid and ATS-readable PDF, understand
> every blocker and available action, and track the recruitment process through either
> Web or CLI clients backed by the same application layer.

The Web UI makes the v1 engine accessible; it does not replace its safety model. A
normal Web workflow must not require the user to know entity IDs, hashes, filesystem
paths, database details, or architecture. Those details remain available in provenance
views and diagnostic interfaces.

## 3. Product boundaries

- v2.0 is local-first and single-user.
- One Workspace represents one candidate and one canonical knowledge source.
- The domain must not hardcode `Matan`, a particular filename, or another candidate
  identity. A single `CandidateContext` supplies the candidate-specific policy.
- There is no candidate selector, candidate CRUD, or multi-candidate UI.
- FastAPI is the local backend and serves the production React build.
- React, TypeScript, Vite, Tailwind CSS, React Router, TanStack Query, and React Hook
  Form form the frontend baseline. Radix primitives may be used selectively.
- SQLite stores structured state and relationships.
- The filesystem stores immutable or heavy payloads.
- Facts, Profiles, selection policies, prompts, task contracts, and rendering rules
  remain version-controlled files and independent sources of truth.
- The CLI and FastAPI call the same application services directly. The CLI does not use
  HTTP and does not require the Web server.
- v2.0 officially targets macOS. Portable code is preferred, but Windows and Linux do
  not block release.
- The UI supports current Chrome/Chromium with full E2E coverage and current Safari
  with WebKit smoke coverage. PDF rendering always uses Playwright-managed Chromium.

## 4. v2.0 scope

v2.0 includes:

- An isolated, validated local Workspace and `cv web` runtime supervisor.
- A Hebrew, desktop-first Web UI with basic responsive behavior.
- FastAPI `/api/v1` endpoints backed by explicit application use-cases.
- Job creation from required pasted text, an optional provenance URL, and a browser-read
  `.txt` convenience input.
- Immutable JobSnapshots, versioned analyses, immutable SelectionPlans, one mutable
  WorkingDraft, immutable ApprovedRevisions, immutable artifacts, and append-only
  submissions and audit history.
- Duplicate warnings based on identical URL, normalized-text hash, and a light
  company/title heuristic. Duplicates are never blocked.
- Exception-based analysis review and deterministic action policy.
- Track, Profile, Emphasis, language, requirement interpretation, gap classification,
  fact selection, accepted gaps, and pending fact creation through the review flow.
- A structured section/bullet editor, fact inclusion/exclusion, deterministic changes,
  targeted AI regeneration, free-text edits, optimistic autosave, and isolated HTML
  preview.
- Full deterministic validation before approval and browser/PDF/ATS validation after
  rendering.
- Explicit Web approval and immutable provenance for the exact approved content.
- A Ready projection over a qualifying ApprovedRevision.
- Contextual fact inspection and the pending -> confirmed -> canonical -> attached
  lifecycle without a general Knowledge Manager.
- OpenAI Responses API integration for the five v2.0 AI tasks through strict structured
  Proposal contracts.
- A deterministic offline flow through Ready when no OpenAI key is configured.
- A Dashboard, Application Detail, unified timeline, recruitment tracking, next action,
  internal and external submissions, status correction, and overdue warnings after the
  first vertical slice is complete.
- Recruiter-facing PDF download and human-readable provenance/decision Markdown export.
- Full backup, verification, restore, guarded v1 migration, and reconciliation commands.

## 5. Explicit non-goals

The following are not part of v2.0:

- Multiple candidates or candidate administration.
- Authentication, cloud deployment, sync, PostgreSQL, or SQLAlchemy.
- Automatic job extraction from URLs, LinkedIn, or JS-heavy sites.
- Job-description PDF parsing or arbitrary file uploads.
- Additional AI providers or a provider selector.
- Cover letters, LinkedIn messages, recruiter emails, or other document types.
- AI-generated decision explanations.
- AI extraction/linking of arbitrary edited claims.
- Arbitrary user prompts or per-screen model selection.
- A general Knowledge Manager or Web editing of Profiles, policies, prompts, or rules.
- A general WYSIWYG editor, section reordering, or drag-and-drop.
- Mobile-first flows or a full internationalization framework.
- Notifications, calendar integration, recurring reminders, or follow-up automation.
- Charts, advanced analytics, or Web CSV export.
- General CSV/data import beyond the guarded v1 migration.
- WebSocket or SSE progress transport.
- Hard deletion through the Web UI.
- Automatic application or schema updates.

No non-goal may enter v2.0 as a supposedly small convenience without an explicit scope
decision.

## 6. Core invariants

1. `Application` is the container for one target job and its history.
2. The Workspace represents one candidate. Candidate identity is not a dimension on
   every Application row.
3. `WorkingDraft` is the only mutable resume document and there is at most one active
   WorkingDraft per Application.
4. JobSnapshot, JobAnalysis, SelectionPlan, ValidationRun, ApprovedRevision, Artifact,
   Submission, and completed Operation records are immutable/versioned as specified.
5. An approved revision is never edited. Editing it creates a new WorkingDraft with an
   explicit parent revision and source analysis/selection plan.
6. `ReadyRevision` is not an entity. `ready_qualified` is a context-independent
   projection over an ApprovedRevision with exact artifacts, passing render/PDF/ATS
   validation, and successful current integrity verification.
   `PreparationState=ready` is the separate active-context projection of a compatible
   `ready_qualified` revision.
7. `latest_ready_revision_id` always refers to an ApprovedRevision ID.
8. Ready compatibility is defined by JobSnapshot + JobAnalysis, not SelectionPlan. A
   new plan or draft under the same snapshot and analysis does not demote the active
   Ready projection. A new snapshot or analysis removes it from the active projection
   without changing qualification solely because the active context moved. Missing or
   corrupted artifacts may still make `ready_qualified=false`.
9. Approval requires a passing ValidationRun for the exact WorkingDraft ID,
   `edit_version`, content hash, facts and knowledge context, analysis context, and
   validator versions being approved.
10. Changing one character after validation makes that ValidationRun ineligible for
    approval.
11. Unsupported, pending, unlinked, strengthened, or semantically unverified claims may
    be saved in the editor but must block approval.
12. The presence of a valid fact ID does not prove that generated wording is supported;
    semantic factual validation remains mandatory.
13. AI outputs are Proposals. Schema validation, deterministic policy, factual
    validation, and application commit decide what becomes state.
14. AI failure never triggers a silent deterministic fallback. The user may explicitly
    retry or continue deterministically.
15. A provider output, cancelled output, or stale-operation output may exist as inactive
    immutable evidence, but it never becomes current without a successful optimistic
    commit against its original preconditions.
16. Recruitment lifecycle and preparation lifecycle are independent.
17. Recruitment history is append-only. Corrections add events and never rewrite past
    events.
18. Submitted artifacts, ApprovedRevisions, and migrated historical evidence are never
    overwritten or automatically deleted.
19. SQLite owns structured state and relationships; the filesystem owns immutable/heavy
    payloads; Knowledge files own canonical knowledge. No mutable content has two
    simultaneous sources of truth.
20. Every approved output stores exact provenance sufficient to identify its candidate
    context, job context, knowledge context, policies, prompts, provider execution, and
    artifacts.
21. Normal queries never expose partially committed cross-store mutations.
22. Web and CLI concurrency must remain correct through optimistic versions, atomic
    SQLite claims, leases, idempotency where required, and commit-time precondition
    checks.
23. No cutover is performed to discover whether v2 works. v2 must be proven on a
    faithful copy first.

## 7. Candidate and Workspace behavior

One CandidateContext is loaded from Knowledge. It points to canonical identity and
contact fact IDs and supplies display/filename policy, locale, and timezone. Candidate
names and contacts remain canonical facts rather than duplicated metadata.

The recruiter-facing filename uses a configured Latin candidate name by default,
including for Hebrew CVs:

`Matan Malka - <Normalized Target Role> - CV.pdf`

CandidateContext may explicitly override the filename name. Renderers and filename
normalizers receive CandidateContext and must not contain a candidate literal.

The Workspace has explicit roots for knowledge, state, artifacts, temporary files, and
logs. It has a durable Workspace ID and marker. The runtime has a separate installation
ID. Development, copy, test, and live data classes are explicit metadata, not inferred
from directory names.

## 8. Job intake and snapshots

The initial form requires company, target role, and full job text. Source URL is
optional. Source label and notes belong to Application Detail and do not burden the
creation form.

Creating an Application is deterministic and fast. It creates the Application and its
first immutable JobSnapshot; it does not call AI or automatically analyze. Analysis is
a separate action.

The backend stores the exact text string it received without line-ending normalization.
It stores a source hash over that received representation and a separate normalized
hash for deduplication. A browser-read `.txt` file only populates the editable text
area; no file is uploaded. URL is provenance only, is never fetched, and uses soft
syntax validation plus explicit length/control-character limits.

Editing job text creates a new immutable JobSnapshot. The old snapshot and every
analysis/revision linked to it remain historically valid for their own context.

Duplicate detection runs before creation for UX and again inside the create command.
The user may open an existing Application or explicitly create another. Duplicate
results are warnings, never blockers.

## 9. Analysis, selection, and review

JobAnalysis owns requirement interpretation, classification, fit, gaps, and ambiguity.
SelectionPlan owns selected, excluded, and pinned facts, content emphasis overrides,
candidate context, and explicit accepted gaps. Both are immutable and versioned.

Every successful `analyze_job` commit creates both the immutable JobAnalysis and one
initial deterministic SelectionPlan for that exact analysis. The plan is produced by
the deterministic selection policy and freezes its own policy/candidate-context
versions. An AI `propose_selection_plan` task is an optional, separate Operation that
may propose a replacement plan; it is never required to make the no-review path
draftable.

A change to the meaning or classification of a requirement creates a JobAnalysis. A
change only to which facts will address an already understood requirement creates a
SelectionPlan.

Analysis review is exception-based. When no material decision is required and the
global auto-generation setting is enabled, the workflow may continue to drafting.
Review is required only for active-context reasons such as material ambiguity, low fit,
a hard gap requiring an explicit decision, unresolved fact selection, or a pending fact
on which the active plan or claim depends.

Accepted gaps live in SelectionPlan. Acceptance records gap ID, analysis ID, actor, and
timestamp, with an optional reason. It means only that the user knowingly proceeds; it
never changes a gap to satisfied or authorizes an unsupported claim.

Analysis Review is a local form. Applying its decisions creates one new immutable
version rather than one version per toggle.

## 10. Drafting and editing

DraftDocument structured data is the source of truth. Mutable JSON and mutable Markdown
must not coexist as independent sources. Markdown and HTML are projections.

The editor primarily works with sections and bullets. Each claim exposes its text,
linked facts, claim status, warnings, and edit/regenerate/remove controls. Section order
is policy-controlled. v2.0 may offer simple up/down bullet controls if needed but does
not include drag-and-drop.

A deterministic selection change creates a new SelectionPlan and synchronously updates
the WorkingDraft only when it requires no AI and contains no semantic ambiguity. A
semantic or rewording change creates the new plan and then runs a regeneration
Operation.

Free-text edits are preserved even when unsupported. They become pending or unlinked,
are immediately visible as unsafe, and block approval until linked through an allowed
deterministic path, converted into a canonical fact lifecycle, or removed. v2.0 does
not use AI to extract and authorize such claims.

Autosave uses debounce/blur and optimistic concurrency. A stale save returns a conflict
and does not overwrite. The UI shows the user's text and the current text for an
explicit choice; it performs no automatic merge.

Preview is server-rendered from the current DraftDocument through the same rendering
pipeline used for approved content where possible. It appears in an isolated iframe,
is clearly marked as draft, and does not generate a PDF on every edit.

## 11. Validation, approval, rendering, and Ready

Editing runs lightweight claim, structure, and required-field checks. A full
deterministic ValidationRun is explicit before approval. Browser/PDF/ATS checks run
only after an ApprovedRevision is rendered.

A failed ValidationRun is a successful domain result with `passed=false` and structured
issues. An exception is reserved for a validator that could not run.

Warnings are visible and non-blocking. Approval may require one general confirmation
that warnings remain. Any item requiring a specific business decision is a blocker or
review reason rather than a warning.

Web approval is always an explicit trust-boundary action. It creates an immutable
ApprovedRevision and clears `active_working_draft_id`; the approved content and lineage
remain frozen in the revision rather than as an active mutable draft. Rendering is a
separate use-case and may be chained by the UI. A render failure does not revoke
approval; the user may retry or explicitly create a new WorkingDraft from that
revision. `newer_draft_in_progress` becomes true only after such a later draft is
created.

The v1 `cv fast` workflow remains available as a CLI compatibility command. Invoking
it is itself an explicit user approval instruction and is recorded with
`actor_type=user`, `client=cli`. It may chain exact validation, approval, rendering,
and Ready checks, but it never bypasses blockers or validation and never auto-approves
merely because an AI Operation completed.

A prior Ready projection remains usable while a newer SelectionPlan or WorkingDraft is
in progress under the same JobSnapshot and JobAnalysis. The UI shows `Ready` and
`newer_draft_in_progress`. A new snapshot or analysis makes the prior Ready projection
historical for the active context and exposes a warning while preserving its files.
The context change alone does not affect `ready_qualified`; artifact/integrity checks
still do.

The Ready screen contains preview, recruiter-facing PDF download, validation summary,
revision/provenance summary, and creation of a new WorkingDraft. Submission is added in
the later tracking milestone, not the first vertical slice.

## 12. AI behavior

v2.0 implements one OpenAI adapter behind the provider-neutral `AIProvider` protocol.
The five AI tasks are:

- `propose_job_analysis`
- `propose_selection_plan`
- `draft_resume`
- `regenerate_section`
- `regenerate_claim`

Each task has explicit input/output schemas, semantic contract version, prompt version
and hash, and structured output validation. Calls are stateless and do not depend on a
prior response or hidden conversation.

The provider receives only the relevant JobSnapshot, allowed facts, required analysis
or plan, and policies needed for the task. It does not receive the entire fact store or
historical artifacts by default. The UI explains that job descriptions and relevant
profile facts may be sent when AI is enabled; no per-call consent dialog is required.

An OpenAI key is backend/environment configuration only. It is never stored in SQLite,
sent to React, or written to logs. Settings expose only whether it is configured.

When a key is configured, `ai_enabled` defaults to true. Commands still choose an
explicit `ai` or `deterministic` mode. There is no ambiguous `auto` execution mode, no
model picker, and no dynamic model discovery. Default model and per-task overrides live
in configuration, and exact provider/model metadata is stored on every run.

Parsed output and a sanitized raw response are preserved. Raw responses are immutable
artifacts rather than SQLite blobs. Response ID, model, usage, latency, hash,
refusal/error metadata, and contract/prompt versions are recorded. Secrets and hidden
chain-of-thought are never retained.

Job descriptions and user content are untrusted data. They may influence the proposed
content but never policy, allowed facts, validation, approval, or output schemas.

## 13. Preparation and recruitment

Preparation and recruitment are separate views.

`PreparationState` is one of:

- `needs_analysis`
- `needs_review`
- `ready_to_draft`
- `draft_in_progress`
- `ready_for_approval`
- `approved`
- `ready`

`WorkingDraftState` is one of:

- `none`
- `editing`
- `validation_failed`
- `validated`
- `stale`

An optimistic save conflict is a transient session outcome, not an intrinsic
WorkingDraftState unless a future durable conflict entity is introduced.

`RecruitmentStatus` is one of:

- `saved`
- `applied`
- `recruiter_screen`
- `interview`
- `assignment`
- `final_stage`
- `offer`
- `accepted`
- `rejected`
- `withdrawn`
- `closed`

`closed` is archival, not an outcome. The last terminal outcome remains available as a
transactionally consistent projection and in history.

Every Application projection includes current preparation and draft states, active
context IDs, latest approved/ready references, review and stale reasons, active
Operation, warnings, available actions, blocked actions with reason codes, a nullable
recommended action, and the `newer_draft_in_progress` flag. These values are computed
within one consistent read transaction.

The backend owns action policy. React and CLI do not implement a second state machine.

## 14. Recruitment tracking

The first architectural slice ends at Ready. After that gate passes, v2.0 adds a table
Dashboard with search, filters, sorting, preparation/recruitment state, last activity,
next action/date, active Operation, and warnings. It does not include charts.

Application Detail contains header/status/next action, current preparation, one unified
timeline, focused revisions/artifacts and submissions sections, and navigation back to
the editor.

`submit_application` verifies an explicit `ready_qualified` ApprovedRevision and exact
PDF artifact, creates an immutable Submission, transitions to `applied` if necessary,
and appends status/audit history in one SQLite transaction. It never resolves `latest`
inside the command. The revision need not match the current active snapshot/analysis;
that case returns `READY_REVISION_FOR_OLDER_SNAPSHOT` or
`READY_REVISION_FOR_OLDER_ANALYSIS` as a non-blocking historical-context warning.
Multiple submissions are append-only and do not reset recruitment state.

`record_external_submission` is a distinct use-case. It may reference a file already
known to the system but never invents an ApprovedRevision or Artifact.

Backward transitions are not ordinary business transitions. A status error is fixed by
an explicit correction event with the corrected event ID and mandatory reason. The
current status is stored as a transactionally consistent projection; events provide
audit history rather than event-sourced reconstruction.

One next action and date may be active for an Application. Changes append events.
Overdue is a computed warning when the date is before today and the Application is not
terminal. There are no notifications in v2.0.

There is no hard delete through Web. Applications created by mistake may move from
`saved` to `closed`.

Audit actor identity is intentionally local and non-authenticated:

```text
actor_type: user | system | migration
client: web | cli | worker
installation_id
```

The primary UI may display `You` for `actor_type=user`; technical client identity
belongs to provenance rather than the normal timeline label.

## 15. Runtime and local security

`cv web` is a runtime supervisor, not a shell alias for Uvicorn. It validates the
Workspace and schema, detects the process/port state, builds the composition root,
starts FastAPI and the Operation worker, opens the default browser unless `--no-open`
is supplied, and performs graceful shutdown.

The default endpoint is `127.0.0.1:8765`. If that endpoint belongs to the same
installation/Workspace, the existing instance is opened. If another process owns it,
the supervisor chooses a free port and reports/opens it.

Production serves the built React application from FastAPI under the same origin. The
server binds only to loopback, has no wildcard CORS, and validates `Origin` on mutating
requests. Development allows only the explicit Vite origin. v2.0 does not add user
authentication or a CSRF token.

Node and frontend development details are not runtime requirements for the user.
Playwright-managed Chromium is the normal renderer. Local Chrome is a diagnostic/manual
fallback only and is never selected silently.

Safe UI settings in v2.0 are limited to automatic generation when review is not
required, `ai_enabled`, default execution mode (`ai` or `deterministic`), basic UI
preferences, and `open_browser_on_launch`. Model/task overrides, Workspace roots,
timezone, and secrets remain backend/Workspace configuration.

## 16. Storage, provenance, and retention

SQLite stores Applications, analyses, SelectionPlans, WorkingDraft, ValidationRun
metadata/reports, Operations, artifact metadata, submissions, settings, and audit.

The filesystem under `artifacts_root` stores:

```text
snapshots/{application_id}/{snapshot_id}.txt
revisions/{application_id}/{revision_id}/resume.json
revisions/{application_id}/{revision_id}/resume.md
outputs/{application_id}/{revision_id}/{artifact_id}.html
outputs/{application_id}/{revision_id}/{artifact_id}.pdf
```

Screenshots, manifests, sanitized provider responses, and other immutable payloads use
the same ID-based policy. Friendly filenames exist only at export/download. Paths are
never API inputs and are validated against their configured root before access.

Each approved revision records a global knowledge-store version for coarse audit and an
exact knowledge context containing the facts, candidate context, Profile, candidate
pool, Track/Emphasis rules, selection/rendering policies, prompt/task contracts, and
their hashes. An unrelated fact change does not automatically stale every draft.

A SelectionPlan records candidate fact IDs and hashes, Profile version, selection
policy version, and every Track/Emphasis dependency. These immutable contexts determine
staleness without rewriting past plans.

Approved, submitted, historical, and inactive Operation outputs are not automatically
deleted. Temporary orphan files may be cleaned after a configured TTL. Replacing a
WorkingDraft may discard the old working copy after success; an explicit `Keep` archives
it as a historical draft snapshot while preserving only one active WorkingDraft.

## 17. Knowledge lifecycle

Knowledge stays file-based and version-controlled. UI writes follow:

`UI -> KnowledgeRepository -> validate -> atomic file write -> audit event`

The application never performs an automatic Git commit.

New v2 facts receive UUIDv4 technical IDs. Migrated semantic fact IDs are preserved.
The UI does not expose fact-ID creation. A system-generated human slug may exist but is
not identity.

The contextual v2.0 Web flow supports viewing facts, creating a pending fact, explicit
confirmation/promotion, attachment to a Profile section, and use in a new SelectionPlan.
The shortcut `Confirm and add to source of truth` still records
pending -> confirmed -> canonical transitions separately. `Confirm and use` is one
logical command that promotes, attaches, and creates the new plan or reports a complete
failure.

Creating a fact from a claim copies the exact user text without AI rewriting. Meaning,
tags, provenance, dates, and other metadata require explicit input.

Canonical corrections remain a CLI concern in v2.0 and create a new fact with a
`replaces` relationship rather than mutating old content.

Cross-store Knowledge mutations use a narrow durable journal with old/new hashes,
paths, staged path, DB mutation identity, and deterministic recovery. An unreconciled
mutation quarantines additional promotion and approvals that depend on Knowledge, but
does not block read-only history, export, or recruitment tracking.

Superseded facts add historical warnings. A fact known to be incorrect receives a
stronger historical warning. Neither case rewrites an immutable prior revision.

Manual file and CLI Knowledge changes remain supported. Before a relevant command, the
backend re-reads or re-hashes exact dependencies instead of trusting a long-lived
cache. A change produces `knowledge_changed`/`SOURCE_CHANGED`; it is never silently
reloaded into an editor form currently open by the user.

## 18. Operations and failure behavior

Long-running AI analysis, generation/regeneration, rendering, and materially long
browser validation run as persisted Operations outside HTTP requests. Ordinary saves,
approval, selection editing, and recruitment status changes remain synchronous.

Operation lifecycle is:

- `queued`
- `running`
- `succeeded`
- `failed`
- `cancelled`
- `interrupted`

Failure reason is a separate machine-readable code such as `SOURCE_CHANGED`,
`PROVIDER_TIMEOUT`, `INVALID_OUTPUT`, or `RENDER_FAILED`; it is never added to the status
enum.

v2.0 permits one mutating Operation per Application, one global render/browser
Operation, and low AI concurrency with a default ceiling of two. Locks are resource
specific rather than one global mutex.

Operations store a full structured, secret-free payload and hash, resource IDs,
expected versions/hashes, provider/model, timestamps, phases, safe user message,
technical log reference, and failure metadata. The shared Operation runner uses atomic
SQLite claiming, leases, and heartbeat. Under `cv web`, the supervisor hosts background
worker loops. A standalone CLI command that creates an Operation atomically claims and
executes that Operation in the foreground in the same CLI process, using the identical
runner, lease, heartbeat, idempotency, and commit checks; it never requires FastAPI or
`cv web`. Expired queued/running work becomes `interrupted` after restart; AI/browser
work is never resumed mid-call.

Queued cancellation is immediate. Running cancellation is best-effort and prevents
activation. A completed output after cancellation is recorded as inactive evidence.
Retry creates a new Operation with `retry_of_operation_id` and a new idempotency key.

Analyze, generate, approve, and render use idempotency. The scope is installation ID +
operation type + key. Reuse with the same payload hash returns the original result;
reuse with another hash fails. Automatic retry is limited to one delayed attempt for
explicit transient network/provider/browser-startup failures.

## 19. API and UX contracts

The HTTP API is `/api/v1`. It is resource-oriented with action endpoints for real
use-cases. Asynchronous work returns `202 Accepted` and an Operation `Location`.
Synchronous entity creation returns `201 Created`.

API request/response DTOs are explicit Pydantic models separate from domain objects,
database rows, and filesystem paths. OpenAPI produces generated TypeScript types; a
small handwritten client performs requests. CI fails on generated-type drift.

WorkingDraft HTTP updates use ETag/If-Match and return `409 Conflict` on mismatch.
Domain precondition failures such as stale validation return `412`. Problems use a
stable Problem Details body with machine code and safe context. Technical details stay
in logs.

NeedsReview and `ValidationRun(passed=false)` are successful domain outcomes, not HTTP
errors. The API enforces an explicit body-size limit; oversized job text returns
`413 Payload Too Large`.

Artifacts are accessed only by artifact ID. Download resolves and contains the local
path, verifies integrity/root containment, and supplies a friendly Content-Disposition
filename. No general path endpoint exists.

The existing CLI data export is reviewed for actual consumers during M1. A retained
export uses a versioned v2 schema by default. `--legacy-format` is added only when a
real existing consumer is identified; v2 does not create speculative compatibility.

## 20. Migration, rollout, and release states

All development and migration rehearsal use isolated copies. There is no dual-write or
bidirectional synchronization between v1 and v2.

Rollout stages are:

1. Alpha on a test Workspace.
2. Beta on a fresh faithful copy of the real v1 Workspace.
3. Release Ready after full engineering, migration, backup/restore, and acceptance
   evidence.
4. User-approved cutover of the frozen live Workspace.
5. Live after migration, reconciliation, acceptance, and activation succeed.

`Engineering Complete`, `Release Ready`, `Cutover Complete`, and `Live` are distinct.
The v2.0 software may be complete and Release Ready before the separate live cutover
event.

Cutover follows:

`freeze v1 writes -> backup -> verify -> migrate -> reconcile -> full acceptance -> activate v2`

Rollback restores or reuses the frozen v1 snapshot and restarts v1. There is no v2
database downgrade.

## 21. v2.0 Definition of Done

v2.0 is Release Ready only when all of the following are demonstrably true:

- [ ] `cv web` starts an isolated validated Workspace without manual Python/Node steps.
- [ ] Web and CLI use the same application layer and permission policy.
- [ ] One Application completes the full Web vertical slice through Ready PDF.
- [ ] The central failure paths are exercised through the same slice.
- [ ] Review is exception-based and every review reason is explicit and resolvable.
- [ ] The deterministic offline workflow completes through Ready.
- [ ] The five AI tasks return Proposals and cannot bypass deterministic policy.
- [ ] Unsupported or unlinked edits are preserved but cannot pass approval.
- [ ] Approval is bound to one exact WorkingDraft, validation, knowledge context,
      snapshot, analysis, and SelectionPlan.
- [ ] Ready resolves to an exact ApprovedRevision and exact passing artifacts.
- [ ] Current preparation, blockers, staleness, active work, actions, and Ready state are
      understandable from the UI without opening logs.
- [ ] Normal Web use does not require technical IDs, hashes, paths, or architecture.
- [ ] Concurrent CLI/Web saves and Operations preserve all invariants.
- [ ] Idempotency, cancellation, retry, lease expiry, and SOURCE_CHANGED behavior pass.
- [ ] Knowledge journal recovery is deterministic or explicitly quarantined under every
      tested crash window.
- [ ] Dashboard, timeline, tracking, internal/external submissions, corrections, and
      next actions work after the vertical-slice gate.
- [ ] Hebrew UI, Hebrew/English CV preview, RTL/LTR behavior, Chrome, and Safari checks
      pass at their defined coverage levels.
- [ ] Backup is verified, restored, opened, and reconciled.
- [ ] v1 migration succeeds on a faithful copy with zero unexplained records/files.
- [ ] Every applicable v1 safety and regression test remains represented and passing.
- [ ] Linux/Chromium CI passes and macOS release verification passes.
- [ ] A manual OpenAI smoke run records valid structured analysis/draft output and
      execution metadata.
- [ ] An acceptance report records pass, fail, and remaining evidence for every item.

## 22. Change and stop conditions

Implementation proceeds without approval pauses for naming, folder structure, or other
internal details that preserve contracts. Work stops for an unresolved semantic
conflict, scope expansion, migration/data-loss risk, a path that could allow unsupported
claims through approval, a required deployment-model change, or any proposed dual-write
behavior.

## 23. Deferred v2.x candidates

Deferred work may include companion application documents, AI-generated decision
explanations, AI-assisted semantic claim linkage, a broader Knowledge UI, CSV Web
export, notifications, calendar integration, analytics, richer editing interactions,
additional providers, i18n, and later hosted or multi-candidate operation. These are
candidates, not commitments.

## 24. Decision log

This section remains empty at initial approval. Later entries record only approved
changes to this specification, with date, rationale, affected contracts, migration
impact, and acceptance changes. It is not a transcript of planning discussions.
