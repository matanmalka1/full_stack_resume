# v2.0 State and Use-Case Contracts

Status: **Approved for v2.0 implementation (2026-08-17)**

PostgreSQL transaction terminology amendment: **2026-08-25**

Product authority: `docs/spec/product-spec.md`

## 1. Purpose

This document defines the detailed lifecycle, state projections, commands, queries,
outcomes, and action policy exposed through the API. It is normative for behavior but
must not override the product specification.

Commands always name the immutable sources they act on. Query/UI conveniences may
resolve a latest or active entity for presentation; commands may not silently do so.

## 2. Entity lifecycle summary

Mutable:

- Application recruitment projection and safe mutable metadata
- one active WorkingDraft per Application
- one active next action per Application

Immutable/versioned or append-only:

- JobSnapshot
- JobAnalysis
- SelectionPlan
- ValidationRun
- ApprovedRevision
- Artifact and artifact payload
- Submission
- recruitment/status/audit events
- completed Operation lifecycle record
- historical draft snapshot when explicitly kept

`ready_qualified` is a context-independent qualification projection of an
ApprovedRevision and its exact artifacts; it is not another entity.
`PreparationState=ready` is the compatible active-context projection.

## 3. Active context and milestones

The active preparation context contains explicit references:

```text
active_job_snapshot_id
active_analysis_id
active_selection_plan_id
active_working_draft_id
```

Approved revisions, including those that are `ready_qualified`, are immutable
milestones and are not active context merely because they are newest. Query projections
additionally expose:

```text
latest_approved_revision_id
latest_ready_revision_id
newer_draft_in_progress
```

`latest_ready_revision_id` is the newest currently `ready_qualified` ApprovedRevision
across the complete Application history, not the newest revision compatible with the
active context. Compatibility is expressed separately by PreparationState and
historical-context warnings.

Ready compatibility is JobSnapshot ID + JobAnalysis ID. A SelectionPlan or WorkingDraft
change under the same pair does not demote `PreparationState=ready`. A JobSnapshot or
JobAnalysis change makes that milestone historical for the active context without
changing qualification solely because context moved. Missing or corrupt artifacts can
still make `ready_qualified=false`.

## 4. PreparationState

Values:

```text
needs_analysis
needs_review
ready_to_draft
draft_in_progress
ready_for_approval
approved
ready
```

Projection rules use the following exact precedence and are evaluated within one
consistent read transaction. The first matching rule wins:

1. No compatible JobAnalysis for the active JobSnapshot -> `needs_analysis`.
2. A compatible `ready_qualified` ApprovedRevision exists -> `ready`.
3. A compatible ApprovedRevision exists without Ready qualification -> `approved`.
4. The active analysis/plan has an unresolved explicit decision -> `needs_review`.
5. The active WorkingDraft is stale -> `needs_review` only when a real decision is
   required, otherwise `ready_to_draft`.
6. The active WorkingDraft has an exact passing eligible ValidationRun ->
   `ready_for_approval`.
7. An active WorkingDraft exists without such a ValidationRun -> `draft_in_progress`.
8. A compatible analysis and initial/active SelectionPlan exist -> `ready_to_draft`.

Milestone capability therefore takes precedence over parallel work under the same
compatible JobSnapshot + JobAnalysis. A compatible Ready revision plus an unresolved
review reason or newer editing draft still projects `ready`; the review reasons,
blocked actions, WorkingDraftState, and `newer_draft_in_progress` describe the newer
parallel work without erasing the usable milestone. The same rule applies to
`approved`.

When the active JobSnapshot or JobAnalysis changes, old approved/ready milestones remain
historical references but do not participate in active PreparationState.

## 5. WorkingDraftState

Values:

```text
none
editing
validation_failed
validated
stale
```

- `none`: no active WorkingDraft.
- `editing`: an active draft exists and no exact latest validation determines another
  state.
- `validation_failed`: the latest ValidationRun for the exact current version/hash
  passed execution and has `passed=false`.
- `validated`: an eligible ValidationRun exists for the exact current version/hash and
  has `passed=true`.
- `stale`: a source dependency required by the draft no longer matches its frozen
  context.

An ETag conflict is a save-attempt outcome held by the client until resolution. It is
not a persisted WorkingDraftState without a future durable DraftConflict entity.

## 6. Staleness

Structured stale reasons include:

```text
JOB_SNAPSHOT_CHANGED
ANALYSIS_REPLACED
SELECTION_PLAN_REPLACED
FACT_CHANGED
PROFILE_CHANGED
POLICY_CHANGED
DRAFT_EDITED_AFTER_VALIDATION
```

Queries return all reasons plus deterministic `primary_stale_reason`. Staleness does not
itself imply review. A stale draft projects `needs_review` only when a real unresolved
user decision exists; otherwise it projects `ready_to_draft` with replace/archive
actions.

An unrelated Knowledge change does not stale a draft. Exact dependency hashes decide.

## 7. Review reasons

Review reasons are blockers that require an explicit user decision. Initial codes are:

```text
MATERIAL_CLASSIFICATION_AMBIGUITY
LOW_FIT_REQUIRES_ACCEPTANCE
HARD_GAP_REQUIRES_DECISION
FACT_SELECTION_UNRESOLVED
PENDING_FACT_REQUIRES_RESOLUTION
KNOWLEDGE_RECONCILIATION_REQUIRED
```

`PENDING_FACT_REQUIRES_RESOLUTION` applies only when the active SelectionPlan, active
claim, requested selection, or active gap resolution depends on that fact. Pending
facts elsewhere in Knowledge do not affect unrelated Applications.

Each reason includes a safe message, relevant entity references, and allowed resolution
action identifiers.

## 8. Warnings, blockers, and failures

- A warning is important but does not disable approval.
- A blocker disables one or more commands.
- A review reason is a blocker requiring explicit human judgment.
- An error is a technical or Operation failure rather than domain state.

Examples of historical warnings include:

```text
READY_REVISION_FOR_OLDER_SNAPSHOT
READY_REVISION_FOR_OLDER_ANALYSIS
FACT_SUPERSEDED
FACT_KNOWN_INCORRECT
NEXT_ACTION_OVERDUE
```

`FACT_KNOWN_INCORRECT` is materially stronger than supersession but does not rewrite an
immutable historical revision.

## 9. Action policy projection

Application Detail and relevant list projections return:

```json
{
  "recruitment_status": "saved",
  "terminal_outcome": null,
  "preparation_state": "draft_in_progress",
  "working_draft_state": "validation_failed",
  "review_reasons": [],
  "stale_reasons": [],
  "primary_stale_reason": null,
  "warnings": [],
  "active_operation": null,
  "active_job_snapshot_id": "...",
  "active_analysis_id": "...",
  "active_selection_plan_id": "...",
  "active_working_draft_id": "...",
  "latest_approved_revision_id": null,
  "latest_ready_revision_id": null,
  "newer_draft_in_progress": false,
  "available_actions": ["validate", "regenerate_claim"],
  "blocked_actions": [
    {"action": "approve", "reasons": ["VALIDATION_FAILED"]}
  ],
  "recommended_action": "validate"
}
```

The complete projection is computed in one read transaction. `recommended_action` is
deterministic and nullable. Action identifiers are stable application commands, not UI
labels.

## 10. RecruitmentStatus

Values:

```text
saved
applied
recruiter_screen
interview
assignment
final_stage
offer
accepted
rejected
withdrawn
closed
```

Normal transitions:

```text
saved
  -> applied | withdrawn | closed

applied
  -> recruiter_screen | interview | rejected | withdrawn | closed

recruiter_screen
  -> interview | assignment | rejected | withdrawn | closed

interview
  -> assignment | final_stage | offer | rejected | withdrawn | closed

assignment
  -> interview | final_stage | offer | rejected | withdrawn | closed

final_stage
  -> offer | rejected | withdrawn | closed

offer
  -> accepted | rejected | withdrawn | closed

accepted | rejected | withdrawn
  -> closed
```

Backward transitions are not normal. `correct_recruitment_status` adds a correction
event referencing the erroneous event and requiring a reason. Current status and
terminal outcome are updated transactionally while the original event remains.

`closed` is archival. The last accepted/rejected/withdrawn outcome remains in
`terminal_outcome` and history.

Audit actors use `actor_type=user|system` and `client=web|worker`. There is no
authenticated username in v2.0; the UI may label the local user as `You`.

Preparation commands never alter RecruitmentStatus. Drafting after `applied` leaves the
Application applied.

## 11. Operation lifecycle

Status:

```text
queued
running
succeeded
failed
cancelled
interrupted
```

Failure reason is separate. Stable initial failure codes include:

```text
SOURCE_CHANGED
PROVIDER_TIMEOUT
PROVIDER_RATE_LIMITED
PROVIDER_UNAVAILABLE
PROVIDER_REFUSED
INVALID_OUTPUT
SCHEMA_VIOLATION
RENDER_FAILED
BROWSER_START_FAILED
VALIDATION_EXECUTION_FAILED
CANCELLED_BEFORE_ACTIVATION
```

An Operation may be failed/cancelled while owning an inactive immutable output. Output
existence and output activation are separate.

Operation query fields include status, phase, message, timestamps, failure code, safe
failure detail, retry reference, cancellation state, output references, and the
backend-derived Operation actions currently accepted. The UI polls every one to two
seconds. It does not display fabricated percentages or re-derive lifecycle permissions
from status strings.

## 12. Application commands

### `create_application`

Input:

- company
- target role
- exact job text
- optional source URL
- explicit create-anyway acknowledgement when duplicate matches were shown

Behavior:

- validate size/control-character constraints
- compute source and normalized hashes
- rerun duplicate detection
- create Application in `saved`
- write/register immutable initial JobSnapshot
- return warnings and duplicate matches

It is synchronous, deterministic, fast, and never calls AI.

### `create_job_snapshot`

Input: Application ID, exact new text, optional URL/provenance. Creates a new immutable
snapshot, changes active snapshot, and leaves older analyses/revisions historical. It
does not mutate or delete them.

### `close_application`

Transitions a saved/non-terminal Application through the allowed policy to `closed`.
There is no hard-delete command in v2.0 Web.

## 13. Analysis commands

### `analyze_job(application_id, job_snapshot_id, mode, ...)`

Asynchronous and idempotent. It runs deterministic analysis and, in AI mode, a
`propose_job_analysis` task. It validates and merges the Proposal without allowing it to
override hard gaps, factual policy, or schemas. Every successful activation atomically
creates an immutable JobAnalysis and its initial immutable deterministic SelectionPlan,
with the plan's frozen candidate/policy context. It returns both IDs and NeedsReview as
a successful outcome when applicable. This guarantees that the no-review path can call
`create_draft` with explicit source IDs.

Preconditions:

- snapshot belongs to Application
- expected Knowledge/policy inputs still match before activation
- AI mode requires a configured provider

### `apply_analysis_decisions`

Synchronous. It accepts one local form submission. When requirement
meaning/classification changes, it creates one new immutable JobAnalysis together with
that analysis's initial deterministic SelectionPlan. When only selection/accepted-gap
decisions change, it creates one replacement SelectionPlan. It records overrides and
never mutates the original analysis or plan.

### `create_selection_plan`

The deterministic form is synchronous and returns the immutable plan directly. It
receives an explicit analysis ID, candidate context, selected/excluded/pinned facts,
accepted gaps, and policy versions, validates Profile/Track/Emphasis and allowed-fact
constraints, then creates an immutable plan and frozen candidate context.

When AI `propose_selection_plan` mode is requested, the command creates an asynchronous,
idempotent Operation. The provider output is only a Proposal; activation repeats the
same deterministic validations and optimistic source checks before committing the new
plan. No provider call occurs inside a synchronous HTTP request.

## 14. Draft commands

### `create_draft(application_id, analysis_id, selection_plan_id, mode)`

Asynchronous and idempotent for generation. The deterministic path constructs the v1
compatible DraftDocument. AI mode uses `draft_resume` Proposal and semantic validation.
Before activation it confirms Application/snapshot/analysis/plan/Knowledge preconditions
again. It creates or replaces the one active WorkingDraft only after a successful
commit.

When replacement succeeds, the previous working copy may be discarded. If the user
selected Keep, it is first materialized as an immutable historical draft snapshot.

### `update_working_draft`

Synchronous autosave command. Input includes WorkingDraft ID, expected `edit_version`,
and a structured patch. It returns the incremented version/hash. A mismatch returns
Conflict and changes nothing.

Free-text is saved as pending/unlinked when it cannot be authorized. It is not silently
rejected or discarded.

### `apply_selection_change`

Synchronous only when the change is deterministic and unambiguous. It creates an
immutable SelectionPlan and atomically updates the WorkingDraft source/claims. A change
that requires wording judgment returns a precondition/outcome directing the client to a
regeneration command.

### `regenerate_section` / `regenerate_claim`

Asynchronous, idempotent AI Operations. They receive exact WorkingDraft ID/version/hash,
analysis, SelectionPlan, target section/claim, and minimal facts/policies. Output is a
Proposal; activation uses the same optimistic commit rule as draft generation.

### `archive_working_draft`

Synchronous cross-store command that materializes an immutable historical draft
snapshot and clears/replaces the active pointer only after successful registration.

### `replace_working_draft`

Requires an explicit compatible analysis and plan. It does not silently delete a draft
before the replacement is successful.

## 15. Validation and approval commands

### `validate_draft(working_draft_id, expected_version)`

Synchronous for deterministic pre-approval validation. It always creates immutable
ValidationRun when validation executed, including `passed=false`. Validator execution
failure is an application/infrastructure error.

Validation records:

- WorkingDraft ID
- edit version
- content hash
- Application/JobSnapshot/JobAnalysis/SelectionPlan IDs
- exact Knowledge/fact/candidate/Profile/policy context
- validator versions
- issues/groups/evidence

### `approve_draft(working_draft_id, expected_version, validation_run_id)`

Synchronous and idempotent. It requires:

```text
validation.working_draft_id == draft.id
validation.edit_version == draft.edit_version
validation.content_hash == draft.content_hash
validation.passed == true
all analysis/selection/knowledge/validator contexts match
no unresolved blocker or review reason exists
```

It writes immutable revision JSON/Markdown, registers one ApprovedRevision, records the
decision/provenance, deactivates the WorkingDraft, and sets
`active_working_draft_id=null` in the same transaction. The mutable draft is closed;
the ApprovedRevision is its immutable content/lineage record. A later edit or New Draft
action explicitly creates another WorkingDraft with `parent_revision_id`, analysis ID,
and SelectionPlan ID. The same idempotency key/payload returns the same revision. A
reused key with another payload fails.

A no-pause flow is an explicit user approval action. It may orchestrate
validate -> approve -> render -> Ready checks with `actor_type=user` and the
originating client, but it is subject to every exact-validation, warning confirmation,
blocker, and idempotency rule above. No interface offers it in v2.0; the rule binds
whichever one does.

Warnings may require one general confirmation. No warning that actually requires a
specific resolution may reach this command as a warning.

## 16. Rendering commands

### `render_revision(approved_revision_id)`

Asynchronous and idempotent. It validates the exact approved source, writes temp HTML,
renders with Playwright Chromium, generates screenshot/PDF, validates render geometry,
page count, PDF/ATS text, links, direction, filename metadata and integrity, then
registers immutable artifacts.

Render failure leaves ApprovedRevision approved and returns a failed Operation/report.
Retry creates a new Operation. A successful result records the exact passing evidence
needed for the ApprovedRevision to project `ready_qualified`; it projects active Ready
only when its JobSnapshot + JobAnalysis are compatible. It does not create a
ReadyRevision row.

### `export_recruiter_pdf(approved_revision_id, pdf_artifact_id)`

Synchronous read/export. It verifies registration, hash, `ready_qualified`, and path
containment before returning a friendly Content-Disposition filename. Active-context
compatibility is not required to export a historical qualified revision.

### `export_decision_markdown(application_id, approved_revision_id)`

Produces a human-readable provenance/decision export. Diagnostic JSON remains available
through the API but is not the primary human export.

## 17. Knowledge commands

### `create_pending_fact`

Creates a UUID-identified pending fact through the Knowledge mutation journal. Input
contains language-neutral meaning, exact English rendering, optional Hebrew rendering,
tags, provenance, dates/replacement, proposed Profile section, and source
Application/claim. Fact identity is not user-editable.

### `confirm_and_use_fact`

One logical cross-store command:

```text
pending -> confirmed -> canonical
-> attach to explicit Profile section
-> create immutable SelectionPlan
```

Every transition receives a separate audit event. Complete validation occurs before
mutation, the journal provides deterministic recovery, and normal queries never expose
partial completion. A failure reports the whole command as unsuccessful.

### `create_fact_from_claim`

Copies exact claim text into the appropriate rendering without AI rewrite. Meaning,
tags, provenance, and other required metadata are supplied explicitly. It creates a
pending fact and does not authorize the claim until the lifecycle/attachment/plan is
complete.

Canonical correction creates a replacement fact carrying `replaces`; it never mutates
the old fact content.

## 18. Tracking commands

### `submit_application`

Input names Application ID, ApprovedRevision ID, exact PDF Artifact ID, submission time,
and metadata. It verifies the revision's current `ready_qualified` status, exact PDF,
and current artifact integrity; inserts immutable Submission; transitions to `applied`
if required; and appends status/audit events in one PostgreSQL transaction. It never
resolves latest implicitly. Active-context compatibility is not a precondition: when
the active snapshot or analysis is newer, the outcome includes the corresponding
`READY_REVISION_FOR_OLDER_*` warning.

Multiple submissions are allowed. Later submissions do not add a redundant `applied`
transition or reset recruitment state.

### `record_external_submission`

Records an immutable external submission without inventing ApprovedRevision/Artifact.
It may reference an already registered artifact. It transitions to `applied` if
required and records explicit provenance.

### `transition_recruitment_status`

Applies only an allowed forward transition. Actor, client, timestamp, from/to, and
source are mandatory; reason is optional for a normal transition.

### `correct_recruitment_status`

Requires target status, `corrects_event_id`, and reason. It appends a correction event
and updates current status/terminal outcome in one transaction. It does not delete or
alter the corrected event.

### `set_next_action`

Sets or clears the one active action/date and appends an event. Overdue is computed by
queries; no notification job is created.

## 19. Operation commands

### `cancel_operation`

Queued work becomes cancelled immediately. Running work records
`cancellation_requested_at`. Any later output is registered inactive and cannot be
activated.

### `retry_operation`

Creates a new Operation with `retry_of_operation_id` and a new idempotency key. The old
Operation remains immutable. Reusing the old key returns the old result.

## 19a. Settings commands

### `update_settings(expected_edit_version, settings)`

Applies the safe UI settings named in `docs/spec/product-spec.md` section 15. The write
is optimistic: `expected_edit_version` must match the stored one, and a mismatch is a
conflict that changes nothing. Each successful write increments `edit_version`, which the
transport carries as an ETag.

Model and task overrides, timezone, and secrets are not settings. They are backend
configuration and are never writable through this command.

## 19b. Maintenance commands

### `reconcile()`

Checks database references and stored artifact hashes against the payload store, and the
fact lifecycle against its audit trail. Both halves always run: a failing artifact check
must not hide a broken lifecycle.

It reports and never repairs. The records it checks are immutable, so a repair would
destroy the evidence of the mismatch. `passed` is the conjunction of both halves; a
failed reconciliation is a successful answer to the question asked, not a command
failure.

## 20. Queries

Initial query contracts include:

- Application list with search/filter/sort and Dashboard projection
- Application detail with consistent state/action policy and unified timeline
- duplicate candidates for a proposed Application
- active preparation context
- JobSnapshot and analysis history
- SelectionPlan detail and candidate accounting
- WorkingDraft plus ETag
- ValidationRun detail
- ApprovedRevision and Ready qualification detail
- artifact metadata/download eligibility
- Operation status
- contextual fact detail/history
- submissions and recruitment history
- next-action/overdue projection
- runtime/provider configuration status without secrets

Queries may use direct efficient joins and read models. They return DTOs, not database
rows or local paths.

## 21. HTTP mapping baseline

Representative endpoints:

```text
POST   /api/v1/applications
POST   /api/v1/applications/duplicate-check
POST   /api/v1/applications/{id}/job-snapshots
POST   /api/v1/applications/{id}/analyses
POST   /api/v1/analyses/{id}/apply-decisions
POST   /api/v1/analyses/{id}/selection-plans
POST   /api/v1/applications/{id}/working-draft/generate
GET    /api/v1/working-drafts/{id}
PATCH  /api/v1/working-drafts/{id}
POST   /api/v1/working-drafts/{id}/validate
POST   /api/v1/working-drafts/{id}/approve
POST   /api/v1/working-drafts/{id}/regenerate-section
POST   /api/v1/working-drafts/{id}/regenerate-claim
POST   /api/v1/approved-revisions/{id}/render
GET    /api/v1/artifacts/{id}
GET    /api/v1/artifacts/{id}/download
GET    /api/v1/operations/{id}
POST   /api/v1/operations/{id}/cancel
POST   /api/v1/operations/{id}/retry
POST   /api/v1/applications/{id}/submissions
POST   /api/v1/applications/{id}/external-submissions
POST   /api/v1/applications/{id}/recruitment-transitions
POST   /api/v1/applications/{id}/recruitment-corrections
```

Final path names remain an internal design choice if resource identity, explicit source
IDs, and use-case semantics do not change.

`POST /analyses/{id}/selection-plans` returns `201` for deterministic mode and `202`
plus `Location` for AI proposal mode.

## 22. HTTP outcomes

- `200`: query/update or successful outcome such as validation failure
- `201`: synchronous entity creation
- `202`: accepted Operation with `Location`
- `409`: optimistic concurrency or idempotency-key payload mismatch
- `412`: missing/stale domain precondition
- `413`: body limit exceeded
- `422`: invalid request schema
- `500/503`: infrastructure execution failure as appropriate

Problem Details carries stable `code`, safe `detail`, and safe `context`. Examples:

```text
VALIDATION_STALE
VALIDATION_REQUIRED
UNLINKED_CLAIM
IDEMPOTENCY_KEY_REUSED
SOURCE_CHANGED
KNOWLEDGE_RECONCILIATION_REQUIRED
```

NeedsReview and domain validation issues are data, not exceptions.

## 23. First vertical slice

The mandatory sequence is:

```text
Create
-> Analyze
-> Review if required
-> Draft
-> Edit
-> Validate
-> Approve
-> Render
-> Ready
```

Auto-generation is opt-in: the setting is off by default, and drafting continues
automatically only when review is not required *and* the setting has been turned on.
Successful Analyze already returns the explicit initial SelectionPlan ID used by Draft.
The UI may chain commands, but each remains an independent application use-case.

Dashboard and recruitment management may not begin until this path and its central
failure modes pass through both the Application API and the Web UI.
