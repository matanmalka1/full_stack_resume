# CV Application v2.0 Product Specification

Status: **Approved for v2.0 implementation (2026-08-17)**

Persistence, object-storage, secret-configuration, and fixed-root amendments: **2026-08-25**

Product version: **2.0**

Base v1 revision: **`v1.0.0` / `2cc31c7`**

Primary specification language: English

Primary UI language: Hebrew

Official target platform: macOS

## תקציר מנהלים

v2.0 הופך את מנוע v1 המאומת לאפליקציה מלאה למועמד יחיד.
המערכת כוללת FastAPI מקומי, ממשק React בעברית, PostgreSQL ל-state מובנה
ו-object-storage abstraction ל-snapshots ולתוצרים immutable. ברירת המחדל היא
אחסון מקומי, וניתן לבחור bucket תואם S3 בלי לשנות references במסד.
ה-Web הוא ה-client היחיד.
המערכת רצה בשני תהליכים מעל אותה שכבת application: ה-API ו-worker ה-Operations.

הזרימה המרכזית היא:

`Create -> Analyze -> Review if required -> Draft -> Edit -> Validate -> Approve -> Render -> Ready`

Review הוא שער מבוסס חריגים, לא מסך חובה. המערכת ממשיכה אוטומטית ל-draft כאשר
אין ambiguity מהותית, gap הדורש החלטה, claim לא נתמך או בחירת עובדות לא פתורה.
האישור ב-Web תמיד מפורש. WorkingDraft הוא המסמך היחיד שניתן לשינוי;
ApprovedRevision וכל התוצרים הנגזרים ממנה הם immutable.

AI מסווג ומציע ניסוח תחת חוזים מובנים. הוא אינו מקור אמת ואינו יוצר ישויות domain
ישירות. עובדות canonical, policy דטרמיניסטי ו-validation נשארים סמכותיים. מסלול
דטרמיניסטי מלא עד Ready PDF ממשיך לעבוד ללא API key.

הפיתוח מתבצע ב-branch/worktree הפעיל של v2 מול מסד PostgreSQL מבודד.
אין dual-write. v1 הוא ארכיון קפוא ב-Git ואינו נפתח,
נקרא או נכתב על ידי v2 — אין מיגרציה ואין cutover.

## 1. Authority and interpretation

Authority is ordered as follows:

1. This product specification defines binding product semantics, scope, safety, and
   observable behavior after it is approved.
2. `docs/spec/state-and-use-cases.md` defines the detailed state, command, query, and
   permission contracts consistent with this specification.
3. `docs/spec/architecture.md` defines the technical architecture that implements those
   contracts.
4. The implementation and test plans define execution and evidence.

Normative terms such as **must**, **must not**, **should**, and **may** are intentional.
An internal naming or packaging decision may change without approval when observable
behavior and every invariant remain unchanged. A semantic change, scope expansion,
migration risk, or weakened factual boundary requires an explicit decision.

`AGENTS.md` governs repository work and points to this specification set.

## 2. Product goal

> A single candidate can create a job application, analyze the job, resolve only the
> decisions that require human judgment, produce and edit a fact-linked CV, validate and
> explicitly approve one exact revision, render a valid and ATS-readable PDF, understand
> every blocker and available action, and track the recruitment process through either
> Web clients backed by one application layer.

The Web UI makes the v1 engine accessible; it does not replace its safety model. A
normal Web workflow must not require the user to know entity IDs, hashes, filesystem
paths, database details, or architecture. Those details remain available in provenance
views and diagnostic interfaces.

## 3. Product boundaries

- The application represents one candidate and one canonical knowledge source.
- The domain must not hardcode `Matan`, a particular filename, or another candidate
  identity. A single `CandidateContext` supplies the candidate-specific policy.
- There is no candidate selector, candidate CRUD, or multi-candidate UI.
- React, TypeScript, Vite, Tailwind CSS, React Router, TanStack Query, and React Hook
  Form form the frontend baseline. Radix primitives may be used selectively.
- PostgreSQL stores structured state and relationships through SQLAlchemy Core and
  explicit Alembic revisions.
- Immutable or heavy payloads use a storage-neutral object-store boundary. Local
  filesystem storage is the default; an S3-compatible bucket is optional.
- Facts, Profiles, selection policies, prompts, task contracts, and rendering rules
  remain version-controlled files and independent sources of truth.
- The Web UI is the product interface and reaches the system only through the API,
  which is the only user-facing adapter. The Operation worker calls the same application
  layer as an internal execution host; it serves no user. Maintenance is an API concern
  like any other. A second user-facing surface for a use-case the API owns has a second
  contract to keep compatible and no capability the first lacks.
- The API calls the same application services directly; the deterministic workflow
  reaches Ready with no AI key.
- The application officially targets macOS. Portable code is preferred, but Windows and
  Linux do not block release.
- The UI supports current Chrome/Chromium, with full E2E coverage. No other browser is
  claimed, because none is verified. PDF rendering always uses Playwright-managed
  Chromium.

## 4. Scope

The product includes:

- An application rooted in the project, run as an API process and a worker process.
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
- OpenAI Responses API integration for the five AI tasks through strict structured
  Proposal contracts.
- A deterministic offline flow through Ready when no OpenAI key is configured.
- A Dashboard, Application Detail, unified timeline, recruitment tracking, next action,
  internal and external submissions, status correction, and overdue warnings after the
  first vertical slice is complete.
- Recruiter-facing PDF download and human-readable provenance/decision Markdown export.
- Explicit schema upgrade and reconciliation commands. PostgreSQL and remote-bucket
  backup/restore remain environment responsibilities rather than application commands.

## 5. Explicit non-goals

The following are not part of the product:

- Multiple candidates or candidate administration.
- Authentication, multi-user/tenant behavior, sync.
- Additional structured-state databases, ORMs, or broad storage-provider abstractions
  beyond PostgreSQL/SQLAlchemy Core and the local/S3-compatible object stores.
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
- General CSV or data import.
- WebSocket or SSE progress transport.
- Automatic application or schema updates.

No non-goal may enter the product as a supposedly small convenience without an explicit
scope decision.

## 6. Core invariants

1. `Application` is the container for one target job and its history.
2. The application represents one candidate. Candidate identity is not a dimension on
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
7. `latest_ready_revision_id` refers to the newest currently `ready_qualified`
   ApprovedRevision across the Application's full history, regardless of active-context
   compatibility. `PreparationState` and historical-context warnings state whether it
   is compatible with the active JobSnapshot + JobAnalysis.
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
18. Submitted artifacts and ApprovedRevisions are never overwritten or automatically
    deleted.
19. PostgreSQL owns structured state and relationships; the configured object store owns
    immutable/heavy payloads; Knowledge files own canonical knowledge. No mutable content
    has two simultaneous sources of truth.
20. Every approved output stores exact provenance sufficient to identify its candidate
    context, job context, knowledge context, policies, prompts, provider execution, and
    artifacts.
21. Normal queries never expose partially committed cross-store mutations.
22. API and worker concurrency must remain correct through optimistic versions, atomic
    PostgreSQL claims, leases, idempotency where required, and commit-time precondition
    checks.
23. v2 starts with an empty database. It is proven by running its own workflow, not by
    being pointed at existing data to see what happens.

## 7. Candidate and application behavior

One CandidateContext is loaded from Knowledge. It points to canonical identity and
contact fact IDs and supplies display/filename policy, locale, and timezone. Candidate
names and contacts remain canonical facts rather than duplicated metadata.

The recruiter-facing filename uses a configured Latin candidate name by default,
including for Hebrew CVs:

`Matan Malka - <Normalized Target Role> - CV.pdf`

CandidateContext may explicitly override the filename name. Renderers and filename
normalizers receive CandidateContext and must not contain a candidate literal.

Knowledge, artifacts, temporary files, and logs use fixed directories below the project
root. There is no selectable root, marker, or runtime identity file.

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
global auto-generation setting has been turned on -- it is off by default -- the
workflow may continue to drafting.
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
is policy-controlled. The editor may offer simple up/down bullet controls if needed but
does not include drag-and-drop.

A deterministic selection change creates a new SelectionPlan and synchronously updates
the WorkingDraft only when it requires no AI and contains no semantic ambiguity. A
semantic or rewording change creates the new plan and then runs a regeneration
Operation.

Free-text edits are preserved even when unsupported. They become pending or unlinked,
are immediately visible as unsafe, and block approval until linked through an allowed
deterministic path, converted into a canonical fact lifecycle, or removed. The application
does not use AI to extract and authorize such claims.

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

A no-pause flow that chains validation, approval, rendering, and Ready checks is an
explicit user approval instruction and is recorded as one, with `actor_type=user` and
the originating client. It never bypasses blockers or validation and never auto-approves
merely because an AI Operation completed. No interface offers this flow; the
guarantee binds whichever one does.

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

The application implements one OpenAI adapter behind the provider-neutral `AIProvider`
protocol.
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

An OpenAI key is backend/environment configuration only. It is resolved through the
runtime configuration contract but is environment-only: `.env` and project config
cannot enable it. It is never stored in PostgreSQL, sent to React, or written to logs.
Settings expose only whether it is configured.

When a key is configured, `ai_enabled` defaults to true. Commands still choose an
explicit `ai` or `deterministic` mode. There is no ambiguous `auto` execution mode, no
model picker, and no dynamic model discovery. Default model and per-task overrides live
in configuration, and exact provider/model metadata is stored on every run.

Parsed output and a sanitized raw response are preserved. Raw responses are immutable
artifacts rather than PostgreSQL blobs. Response ID, model, usage, latency, hash,
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

The backend owns action policy. React does not implement a second state machine.

## 14. Recruitment tracking

The first architectural slice ends at Ready. After that gate passes, the product adds a table
Dashboard with search, filters, sorting, preparation/recruitment state, last activity,
next action/date, active Operation, and warnings. It does not include charts.

Application Detail contains header/status/next action, current preparation, one unified
timeline, focused revisions/artifacts and submissions sections, and navigation back to
the editor.

`submit_application` verifies an explicit `ready_qualified` ApprovedRevision and exact
PDF artifact, creates an immutable Submission, transitions to `applied` if necessary,
and appends status/audit history in one PostgreSQL transaction. It never resolves `latest`
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
terminal. There are no notifications.

There is no hard delete through Web. Applications created by mistake may move from
`saved` to `closed`.

Audit actor identity is intentionally local and non-authenticated:

```text
actor_type: user | system
client:     web | worker
```

The primary UI may display `You` for `actor_type=user`; technical client identity
belongs to provenance rather than the normal timeline label.

## 15. Runtime and local security

The system runs as two processes over one database: `uvicorn cv_engine.runtime.asgi:app`
serves HTTP and starts no background work, and `python -m cv_engine.worker` claims
queued Operations under a lease. Neither supervises the other; a worker that dies leaves
its claims to expire for the next worker to reclaim.

The default endpoint is `127.0.0.1:8765`. The port is chosen by whoever starts the
process, and the app is told the same value through `CV_API_PORT`, because the origin
policy allows the origin the app believes it answers on. Nothing probes for a free port
or opens a browser.

Production serves the built React application from FastAPI under the same origin. The
server binds only to loopback, has no wildcard CORS, and validates `Origin` on mutating
requests. Development allows only the explicit Vite origin. The application does not add user
authentication or a CSRF token.

Node and frontend development details are not runtime requirements for the user.
Playwright-managed Chromium is the normal renderer. Local Chrome is a diagnostic/manual
fallback only and is never selected silently.

Safe UI settings are limited to automatic generation when review is not
required, `ai_enabled`, default execution mode (`ai` or `deterministic`), and basic UI
preferences. Model/task overrides, timezone, and secrets remain backend/project
configuration.

## 16. Storage, provenance, and retention

PostgreSQL stores Applications, analyses, SelectionPlans, WorkingDraft, ValidationRun
metadata/reports, Operations, artifact metadata, submissions, safe settings, and audit.

The configured object store holds immutable payloads under the same storage-neutral keys:

```text
snapshots/{application_id}/{snapshot_id}.txt
revisions/{application_id}/{revision_id}/resume.json
revisions/{application_id}/{revision_id}/resume.md
outputs/{application_id}/{revision_id}/{artifact_id}.html
outputs/{application_id}/{revision_id}/{artifact_id}.pdf
```

Screenshots, manifests, sanitized provider responses, and other immutable payloads use
the same ID-based policy. `LocalObjectStore` maps keys below `artifacts_root`;
`S3ObjectStore` maps the same keys below the configured bucket/prefix. Database rows keep
the same project-relative references under either backend. Friendly filenames exist
only at export/download. Storage keys and local paths are never API inputs and are
validated before access.

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

New facts receive UUIDv4 technical IDs. Semantic fact IDs survive only in the seed
knowledge carried over from v1, which keeps them; nothing creates new ones.
The UI does not expose fact-ID creation. A system-generated human slug may exist but is
not identity.

The contextual Web flow supports viewing facts, creating a pending fact, explicit
confirmation/promotion, attachment to a Profile section, and use in a new SelectionPlan.
The shortcut `Confirm and add to source of truth` still records
pending -> confirmed -> canonical transitions separately. `Confirm and use` is one
logical command that promotes, attaches, and creates the new plan or reports a complete
failure.

Creating a fact from a claim copies the exact user text without AI rewriting. Meaning,
tags, provenance, dates, and other metadata require explicit input.

Canonical corrections create a new fact with a `replaces` relationship rather than
mutating old content. `POST /api/v1/facts` accepts `replaces`; the new fact enters at
`pending` like any other, so a correction is confirmed and promoted explicitly.

Cross-store Knowledge mutations use a narrow durable journal with old/new hashes,
paths, staged path, DB mutation identity, and deterministic recovery. An unreconciled
mutation quarantines additional promotion and approvals that depend on Knowledge, but
does not block read-only history, export, or recruitment tracking.

Superseded facts add historical warnings. A fact known to be incorrect receives a
stronger historical warning. Neither case rewrites an immutable prior revision.

Manual edits to the Knowledge files remain supported. Before a relevant command, the
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

The application permits one mutating Operation per Application, one global render/browser
Operation, and low AI concurrency with a default ceiling of two. Locks are resource
specific rather than one global mutex.

Operations store a full structured, secret-free payload and hash, resource IDs,
expected versions/hashes, provider/model, timestamps, phases, safe user message,
technical log reference, and failure metadata. The shared Operation runner uses atomic
PostgreSQL claiming, leases, and heartbeat. The worker process hosts the background
worker loops, and the claim contract holds for more than one of them: whichever claims a
row first owns it. Expired queued/running work becomes `interrupted` after restart;
AI/browser work is never resumed mid-call.

Queued cancellation is immediate. Running cancellation is best-effort and prevents
activation. A completed output after cancellation is recorded as inactive evidence.
Retry creates a new Operation with `retry_of_operation_id` and a new idempotency key.

Analyze, generate, approve, and render use idempotency. The scope is operation type +
key. Reuse with the same payload hash returns the original result;
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

Artifacts are accessed only by artifact ID. Download resolves the registered reference,
verifies the stored content hash, and supplies a friendly Content-Disposition filename.
Containment is the backend's: the local store keeps every key below `artifacts_root`;
the S3 store validates the key against its bucket and prefix. No general path endpoint
exists.

Data export uses a versioned v2 schema. A compatibility format is added only when a
real existing consumer is identified; v2 does not create speculative compatibility.

## 20. Rollout and release states

Rescoped on 2026-08-19. v1 is a frozen archive in Git; v2 starts with an empty database
and never reads, migrates, or replaces it. There is no dual-write, no bidirectional
synchronization, and no cutover event.

Rollout stages are:

1. Alpha against an isolated test database and project copy.
2. Beta against the candidate's project Knowledge, used for real work.
3. Release Ready after full engineering, environment-level data-protection verification,
   and acceptance evidence.

`Engineering Complete` and `Release Ready` are distinct; `Cutover Complete` and `Live`
no longer exist as states, because nothing is cut over. Going live means starting to use
v2 for the next application.

Rollback is running v1 from the archive, which needs no preparation: it is a Git
worktree of the frozen commit. There is no v2 database downgrade.

## 21. v2.0 Definition of Done

v2.0 is Release Ready only when all of the following are demonstrably true:

- [ ] The API and worker processes start the local application without manual Node steps.
- [ ] The API enforces the action policy, and the worker executes only persisted
      Operations through the shared Operation runner.
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
- [ ] Concurrent saves and Operations preserve all invariants.
- [ ] Idempotency, cancellation, retry, lease expiry, and SOURCE_CHANGED behavior pass.
- [ ] Knowledge journal recovery is deterministic or explicitly quarantined under every
      tested crash window.
- [ ] Dashboard, timeline, tracking, internal/external submissions, corrections, and
      next actions work after the vertical-slice gate.
- [ ] Hebrew UI, Hebrew/English CV preview, RTL/LTR behavior, and Chrome checks
      pass at their defined coverage levels.
- [ ] Alembic topology and empty-database upgrade pass, and the configured environment's
      PostgreSQL/object-store backup policy is verified outside the application.
- [ ] Every applicable v1 safety invariant and material regression risk remains
      represented and passing. Individual legacy test cases need not be retained when
      a smaller scenario or matrix provides the same failure signal.
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

2026-08-25: Removed the selectable, marked root model. The application now runs from
the project root; marker files, root-selection flags/environment variables, lifecycle
commands, runtime root identity, and root-scoped terminology are removed. Safe settings
now use `app_settings`; migration `0004` performs the schema rename.
