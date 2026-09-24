# v2.0 State and Use-Case Contracts

Status: **Approved for v2.0 implementation**

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

Projection rules use the following exact precedence, using inputs captured in one
consistent database snapshot and payload evidence verified after the read scope closes
(§9). The first matching rule wins:

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
FACT_SELECTION_UNRESOLVED
PENDING_FACT_REQUIRES_RESOLUTION
FACT_DELETED_REQUIRES_RESOLUTION
KNOWLEDGE_RECONCILIATION_REQUIRED
```

Analysis issues, low Fit and hard gaps are diagnostics, not review reasons. They remain
visible to the user but do not require acknowledgement and do not block drafting,
approval, rendering or Ready. Missing evidence is not evidence of missing experience;
an uncertain requirement therefore remains `unknown` rather than becoming unsupported.

A review reason advertises an action only when that action can actually close it. The
projection derives those actions from the underlying fact or integrity condition; it
does not maintain a second catalogue of analysis acknowledgements.

`PENDING_FACT_REQUIRES_RESOLUTION` applies only when the active SelectionPlan, active
claim, or requested selection depends on that fact. Pending
facts elsewhere in Knowledge do not affect unrelated Applications.

`FACT_DELETED_REQUIRES_RESOLUTION` applies only when the active SelectionPlan, active
claim, requested selection, or active gap resolution depends on a fact that has been
deleted (`FactStatus.DELETED`, §17). A deleted fact not referenced by any active
dependency of an Application produces no review reason for that Application; the
immutable ApprovedRevision it may already appear in is unaffected and carries only the
non-blocking `FACT_DELETED` warning (§8).

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
READY_REVISION_FOR_OLDER_SELECTION_PLAN
FACT_SUPERSEDED
FACT_KNOWN_INCORRECT
FACT_DELETED
NEXT_ACTION_OVERDUE
```

`FACT_KNOWN_INCORRECT` is materially stronger than supersession but does not rewrite an
immutable historical revision.

`FACT_DELETED` reports that an ApprovedRevision or WorkingDraft references a fact that
has since been deleted. It is informational only where nothing active depends on the
fact; it never rewrites the immutable revision that already carries the fact's
rendered content. See `FACT_DELETED_REQUIRES_RESOLUTION` (§7) for the blocking case.

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
  "latest_operation": null,
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

All database inputs, including Ready evidence metadata, are captured in one read
transaction. That scope closes before payload verification; the complete projection
is then derived from the captured inputs and verified evidence. This is not an atomic
snapshot across PostgreSQL and object storage. `recommended_action` is deterministic
and nullable. Action identifiers are stable application commands, not UI labels.

`edit_matching_configuration` means voluntarily editing the matching context. It is
committed through the `apply_analysis_decisions` backend endpoint; the latter is an
implementation name, not a separate advertised review action. The voluntary action is available when the Application is not
deleted, an active JobAnalysis exists, and no queued/running Operation can replace the
active JobAnalysis or SelectionPlan.

`active_operation` is limited to queued/running work and is the polling and concurrency
signal. `latest_operation` is the newest lifecycle record whether live or terminal, so a
failed outcome remains presentable after active work ends. A live Operation may therefore
appear in both fields; clients prefer `active_operation` while work is in flight.

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
authenticated username; the UI may label the local user as `You`.

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
CLAIM_REVIEW_UNCERTAIN
CLAIM_REVIEW_UNSUPPORTED
SCHEMA_VIOLATION
RENDER_FAILED
BROWSER_START_FAILED
MISSING_FACT_RENDERING
VALIDATION_EXECUTION_FAILED
CANCELLED_BEFORE_ACTIVATION
PROVIDER_NOT_CONFIGURED
```

`PROVIDER_NOT_CONFIGURED` means an AI task was requested and no provider is configured,
so nothing was sent; `PROVIDER_REFUSED` means a provider answered and refused. Both are
terminal. Operations recorded before `PROVIDER_NOT_CONFIGURED` existed keep the
`PROVIDER_REFUSED` they were recorded with.

`CLAIM_REVIEW_UNCERTAIN` means the semantic reviewer could not establish that a
proposed paraphrase is supported. `CLAIM_REVIEW_UNSUPPORTED` means it found that the
proposal exceeds or contradicts the cited canonical facts. Both are terminal and leave
the current draft active; malformed or incomplete reviewer output remains
`INVALID_OUTPUT`.

An Operation may be failed/cancelled while owning an inactive immutable output. Output
existence and output activation are separate.

Operation query fields include status, phase, message, timestamps, failure code, safe
failure detail, structured failure reason, retry reference, cancellation state, output
references, and the backend-derived Operation actions currently accepted. The UI polls every one to two
seconds. It does not display fabricated percentages or re-derive lifecycle permissions
from status strings.

The structured failure reason is the failure's cause in a closed vocabulary with typed
parameters - a PDF page count against its limit, a fact missing a rendering in a language,
a named render check - written when the failure is recorded. The safe failure detail is
the same cause as an English sentence; a client explains the failure from the reason and
never parses the sentence. The reason is null when the code alone says everything, and on
Operations recorded before the field existed: none is derived after the fact.

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
- report a deterministic intake validation refusal with the rejected field name in safe
  Problem Details context; never reflect the rejected value
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
There is no hard-delete command in the Web UI.

### `delete_application(application_id)`

Soft-deletes an Application: sets a terminal `deleted_at` disposition and appends an
audit event. It is orthogonal to `RecruitmentStatus` — available from any status
including `closed` — and does not itself transition `current_status`. A deleted
Application is excluded from default list/dashboard/search projections and from
duplicate detection, but its record and every immutable JobSnapshot, JobAnalysis,
SelectionPlan, ValidationRun, ApprovedRevision, Artifact, Submission, and Operation it
produced remain unchanged and individually reachable by ID. There is no hard delete and
no `undelete` command in this phase; a mistaken deletion is corrected the same way a
mistaken status is, by explicit reason, not by reversing the flag. Calling it on an
Application already deleted is refused with `StateConflict` (409) — the same idempotency
posture as `delete_fact` refusing an already-`deleted` fact — rather than silently
succeeding again or appending a second `delete_application` audit event.

Every command in §13–§16 that changes or produces state scoped to one Application
(`analyze`, `create_selection_plan`, `apply_analysis_decisions`, the AI proposal forms
of each, `create_draft`, `update_working_draft`, `apply_selection_change`,
`regenerate_section`, `regenerate_claim`, `archive_working_draft`,
`replace_working_draft`, `validate_draft`, `approve_draft`, `render_revision`) resolves
its Application through one shared precondition rather than each service repeating its
own check: 404 if the Application does not exist, 409 (`StateConflict`) if it is
deleted, otherwise the record. A read that must still resolve a deleted Application's
history on purpose — the detail-by-ID projection, `export_recruiter_pdf`,
`export_decision_markdown` — is exempt by design, exactly as §17's `show_fact` stays
exempt for a deleted fact.

## 13. Analysis commands

### `analyze_job(application_id, job_snapshot_id, provider, ...)`

Asynchronous and idempotent. Creating a new analysis requires the configured AI provider.
`analyze_job` runs the one provider task named in product-spec §12,
`propose_analysis`, and supplies its structured Proposal: the posting's requirements with
their importance, evidence-linked coverage, shortfall severity and reason, and the
Track/Profile/Emphasis/language classification. The raw response is preserved.
Deterministic policy locates each quoted
requirement in the snapshot, validates canonical-fact eligibility, refuses a positive
coverage left without evidence, applies canonical boundary facts, checks profile
legality, and derives requirement identity, gaps, Fit, and review reasons. A check that
fails narrows the requirement it names and is recorded as an analysis issue; the rest of
the reading stands. A fact ID or provider-declared
relation is not by itself proof of semantic support or boundary applicability. Unresolved
material completeness, support, or boundary applicability remains explicit and reviewable.
Legacy concept/rule gaps are not unioned into or allowed to veto this result. Every
successful activation atomically
creates an immutable JobAnalysis and its initial immutable deterministic SelectionPlan,
with the plan's frozen candidate/policy context. It returns both IDs and the projected
state. This guarantees that a path without an actual fact or integrity blocker can call
`create_draft` with explicit source IDs.

Preconditions:

- snapshot belongs to Application
- expected Knowledge/policy inputs still match before activation
- a configured provider is available

For AI mode, the application resolves the current allowlisted model and reasoning
preference before writing the Operation. Those values are part of the immutable payload
and runner record; the worker never re-reads Settings to decide what to execute.

### `apply_analysis_decisions`

Synchronous. It accepts one local form submission. When requirement meaning or the
Track/Profile/language classification changes, it creates one new immutable JobAnalysis
together with that analysis's initial deterministic SelectionPlan. An Emphasis decision
changes selection and presentation policy, not the meaning of the analysis; when it is
the only configuration change it is recorded on one replacement SelectionPlan. Fact
Fact-selection decisions likewise create only a replacement SelectionPlan.
When an Emphasis decision accompanies a change that already requires a new analysis, the
new analysis and its initial plan carry that decision in the same atomic write. No branch
mutates the original analysis or plan.

The command serves fact-resolution decisions and voluntary matching-configuration edits.
Every request names the immutable
analysis it addresses and separately carries `expected_analysis_id`; when an active
SelectionPlan exists it also carries `expected_selection_plan_id`. Under the Application
write lock, both expected IDs must still equal the active context. A mismatch returns a
conflict and writes nothing. The same transaction refuses the decision while a queued or
running `analyze_job` or `propose_selection_plan` Operation can replace either context
source. Operation admission and this check serialize on the same Application lock, so a
competing Operation cannot enter between the check and commit.

After a successful commit the API response includes the newly computed application-state
projection, including `available_actions` and `recommended_action`. The Web client chooses
the next step from that projection and does not predict it from the submitted fields. An
existing WorkingDraft that depends on a replaced Analysis or SelectionPlan becomes stale
through the ordinary projection rules. ApprovedRevision and Ready qualification are never
rewritten; when their Analysis is no longer active they remain immutable historical
milestones and the active-context warning rules apply.

A *fact* overlay may not accompany a classification change: pinned and excluded facts
are decided against candidate accounting the new analysis has not produced yet, so they
stay a second command. Historical analyses, plans and decisions are never rewritten.

Fit remains `unknown` when nothing can be scored. An individual requirement whose
coverage is `unknown` receives zero credit without becoming an approval blocker.

`fit_score` is the canonical numeric Fit measure `fit` is read off:
a weighted fraction of requirement coverage (mandatory requirements weighted double),
where `unknown` counts at zero credit rather than being excluded - an incompletely
assessed posting must not outscore a fully assessed one. `fit` (`high`/`medium`/`low`)
is derived from `fit_score` against fixed thresholds, then capped by hard gap count
regardless of the score: two or more hard gaps force `low` outright; exactly one caps
the level at `medium`. This remains diagnostic. `fit_score` is `null` only when nothing
at all could be scored.

A mandatory `unsupported` requirement is a hard gap. A mandatory `partial` requirement
is hard only when its uncovered condition has `material` shortfall severity; `minor` and
`unknown` partial shortfalls are warnings. Coverage values and their numeric Fit credit
do not change: every `partial` still earns one half of its requirement weight.

### `create_selection_plan`

The deterministic form is synchronous and returns the immutable plan directly. It
receives an explicit analysis ID, candidate context, selected/excluded/pinned facts,
an optional explicit Emphasis decision, and policy versions. It validates
Profile/Track/Emphasis and allowed-fact constraints, verifies under the Application lock
that the named analysis is still active, then creates an immutable plan and frozen
candidate context. The manifest distinguishes its effective `emphasis` from nullable
`emphasis_override`, so historical plans remain readable and an explicit choice can
resolve an Emphasis review reason without rewriting JobAnalysis.

When AI `propose_selection_plan` mode is requested, the command creates an asynchronous,
idempotent Operation. The provider output is only a Proposal; activation repeats the
same deterministic validations and optimistic source checks before committing the new
plan. No provider call occurs inside a synchronous HTTP request.

Before a WorkingDraft exists, `create_selection_plan` remains available for an active
analysis even when its initial deterministic plan already exists. This is the explicit
entry to reviewing/replacing that plan or requesting the optional AI proposal;
`create_draft` remains the recommendation when no review decision is outstanding. Once
a WorkingDraft exists, fact-selection changes use `apply_selection_change` so plan and
draft move atomically.

## 14. Draft commands

### Wording evidence contract

The following rules govern generation, regeneration, editing, validation, and approval.
Canonical/extractive/presentation proof or complete eligible reviewed evidence under
product-spec §10.1 may establish claim support. Positive reviewed evidence needs no
individual user confirmation. Uncertainty cannot be downgraded to a warning; known
contradiction or unsupported content cannot be overridden by general approval.

Review execution uses persisted Operations and exact source preconditions. A provider
result with uncertainty is a domain review outcome, not a transport failure, and does
not authorize activation as supported content. Unsupported AI wording remains refused;
unsupported manual text remains savable as pending/unlinked. Evidence cannot be
activated after cancellation or against a newer draft/source context.

A missing/stale review or unresolved clarification blocks approval through both action
policy and application services. Claim-level evidence may remain reusable after an
unrelated edit only when its actual dependencies still match. No previous document
ValidationRun becomes reusable as a consequence. The v1 writer/reviewer flow adds no
public command or PreparationState value. Its provider DTOs carry the exact proposed
claims, section context, linked fact IDs, allowed canonical sources, and one ordered
assertion/source-quote mapping per reviewed claim. Only a fully supported result
activates. Uncertain/unsupported results fail the existing Operation with immutable
inactive provider evidence and leave the current draft unchanged. A later interactive
clarification flow requires its own explicit public DTOs and routes.

### `create_draft(application_id, job_analysis_id, selection_plan_id, provider)`

Asynchronous and idempotent for generation. The deterministic path constructs the
canonical DraftDocument. AI mode uses `draft_resume` Proposal and semantic validation.
Before activation it confirms Application/snapshot/analysis/plan/Knowledge preconditions
again. It creates or replaces the one active WorkingDraft only after a successful
commit.

AI selection-plan proposals, draft generation, and targeted regeneration freeze the same
model/reasoning pair at submission. Retry copies that pair from the original Operation.

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

### `validate_draft(working_draft_id, expected_edit_version)`

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

For reviewed wording, evidence includes exact review/proof references and their
dependency context. Validation checks hard-rule results, full assertion coverage, permitted
evidence kind, no unresolved contradiction/uncertainty, and current source/context
matches. It does not call a provider or infer success from a missing review.

### `approve_draft(working_draft_id, expected_edit_version, validation_run_id)`

Synchronous and idempotent. It requires:

```text
validation.working_draft_id == draft.id
validation.edit_version == draft.edit_version
validation.content_hash == draft.content_hash
validation.passed == true
all analysis/selection/knowledge/validator contexts match
all required claim proof/review evidence is eligible for the exact content and context
no unresolved blocker or review reason exists
```

It writes and verifies immutable revision JSON/Markdown outside database scopes before
registration. One approval transaction rechecks the exact sources, registers the
ApprovedRevision and its artifacts, records decision/audit provenance, deactivates the
WorkingDraft, completes the reserved idempotency receipt when present, and sets
`active_working_draft_id=null`. The mutable draft is closed; the ApprovedRevision is its
immutable content/lineage record. A later return to editing creates another WorkingDraft
from the exact approved manifest, with `parent_revision_id`, analysis ID, and SelectionPlan
ID. It does not recompose the content from the plan and therefore preserves manual edits.
The same idempotency key/payload returns the same revision. A
reused key with another payload fails. Frozen logical payload equality is checked
before returning a committed revision or completing a pending receipt, including
changes to the expected edit version or validation run for the same draft.

A no-pause flow (product-spec.md §11) is an explicit user approval action here too: it
may orchestrate validate -> approve -> render -> Ready checks with `actor_type=user` and
the originating client, but it is subject to every exact-validation, warning
confirmation, blocker, and idempotency rule above.

Warnings may require one general confirmation. No warning that actually requires a
specific resolution may reach this command as a warning.

## 16. Rendering commands

### `render_revision(approved_revision_id)`

Asynchronous and idempotent. It validates the exact approved source, writes HTML and
renders PDF with Playwright Chromium at store-owned render targets, and validates
geometry, page count, PDF/ATS text, links, direction, filename metadata, and integrity.
All rendering, ingestion, and payload verification occur outside database scopes.
Local targets are the stored payloads; remote targets are scratch files uploaded before
cleanup. Render metadata is registered only after all required payloads exist.
Both render artifacts are registered atomically before activation so cancellation or
failed activation preserves inactive evidence. Activation rechecks the frozen sources,
records the post-render ValidationRun bound to the exact PDF even when that report fails,
and activates only eligible outputs in the runner-owned transaction. A failed report is
committed before the Operation is marked failed, so its safe actionable reason remains
available without exposing artifact paths or browser internals.

Render failure leaves ApprovedRevision approved and returns a failed Operation/report.
When correction is needed, the editor offers a direct return to editing: it creates the
new mutable draft from the exact ApprovedRevision in place and keeps the revision-linkage
detail out of the user workflow. It does not strand the user at a retry-only render error
or route through the revision record. Retry creates a new Operation.
A successful result records the exact passing evidence
needed for the ApprovedRevision to project `ready_qualified`; it projects active Ready
only when its JobSnapshot + JobAnalysis are compatible. It does not create a
ReadyRevision row.

### `export_recruiter_pdf(approved_revision_id, pdf_artifact_version_id)`

Synchronous read/export. It verifies registration, hash, `ready_qualified`, and path
containment before returning a friendly Content-Disposition filename. Active-context
compatibility is not required to export a historical qualified revision.

### `export_decision_markdown(application_id, approved_revision_id)`

Produces a human-readable provenance/decision export. Diagnostic JSON remains available
through the API but is not the primary human export.

## 17. Knowledge commands

### `list_facts(status=None)` / `show_fact(fact_id)` / `fact_history(fact_id=None)`

Synchronous reads over the candidate Fact pool and its immutable lifecycle events.
`list_facts` may filter by lifecycle status; with no filter it excludes `deleted` facts,
which remain reachable by an explicit `status=deleted` filter or by `show_fact`.
`show_fact` returns one fact with its events. The dedicated candidate-facts surface uses
these reads without requiring an Application, JobAnalysis, WorkingDraft, or
SelectionPlan context.

### `list_fact_attachment_targets`

Returns the existing Profiles and their sections as read-only attachment targets. Stable
Profile and section identifiers plus display labels are returned; stored paths, Profile
editing capabilities, policies, and other Knowledge documents are not exposed. This is a
query convenience over existing Profile definitions, not candidate or Profile CRUD.

### `create_pending_fact`

Creates a UUID-identified pending fact through the Knowledge mutation journal. Input
contains language-neutral meaning, exact English rendering, optional Hebrew rendering,
tags, provenance, dates/replacement, proposed Profile section, and source
Application/claim. Fact identity is not user-editable.

When `replaces` names a canonical fact, the command creates a pending correction. The
original fact is not mutated; confirmation and promotion remain separate explicit
transitions.

### `confirm_fact(fact_id)`

Moves exactly one fact from `pending` to `confirmed` after explicit user attestation.
It refuses every other source status and never resolves a latest fact implicitly.

### `promote_fact(fact_id)`

Moves exactly one fact from `confirmed` to `canonical` after a second explicit user
attestation. Promoting a replacement makes the original fact superseded for warning and
staleness purposes; it does not rewrite or remove the original record or historical use.

### `delete_fact(fact_id)`

Moves a fact from `pending`, `confirmed`, or `canonical` to the terminal `deleted`
status. Refuses a fact already `deleted`. It is a soft delete through the same
Knowledge mutation journal as every other transition: the fact record and its full
lifecycle history are preserved and remain reachable via `show_fact`/`fact_history`,
but a deleted fact is excluded from `list_facts` by default, from
`list_fact_attachment_targets` results, and is refused by `confirm_fact`,
`promote_fact`, `attach_fact`, and `confirm_and_use_fact`.

Deletion is always permitted, including for a fact currently attached to a Profile
section or referenced by an active SelectionPlan/claim/gap resolution — it does not
require detaching first. Instead, any Application whose active SelectionPlan, claim,
requested selection, or gap resolution depends on the deleted fact reports
`FACT_DELETED_REQUIRES_RESOLUTION` (§7) and is blocked from `approve_draft`/
`ready_qualified` until the dependency is resolved (re-selection, replacement fact, or
equivalent). An ApprovedRevision that already rendered the fact is unaffected and
immutable; it carries only the non-blocking `FACT_DELETED` warning (§8). Deletion never
rewrites, removes, or reassigns the fact's canonical content, and it is a separate
disposition from `replaces`-based canonical correction: deleting a fact does not create
a replacement, and creating a replacement does not delete the original.

### `attach_fact(fact_id, profile, section, pin=False)`

Offers one canonical fact to an explicitly named existing Profile section. It may pin the
fact within that section. It does not edit Profile structure, select the fact for a CV, or
create a SelectionPlan. Non-canonical facts are refused.

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

`delete_fact` (above) is the only removal command in this lifecycle. Archive,
withdrawal, retirement, and distinct `known-incorrect` transitions remain undefined:
adding them requires a separate contract for their effects on Profile pools, selection,
WorkingDraft staleness, warnings, validation, reconciliation, and immutable historical
revisions. Their absence must not be presented by a client as an available action.

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

`MISSING_FACT_RENDERING` and `SOURCE_CHANGED` are not retryable against the same frozen
sources. A missing rendering requires a changed Fact or selection, while a source change
requires a new command frozen against the current source. In both cases the Operation
exposes no `retry` action.

## 19a. Settings commands

### `update_settings(expected_edit_version, settings)`

Applies the safe UI settings named in `docs/spec/product-spec.md` section 15. The write
is optimistic: `expected_edit_version` must match the stored one, and a mismatch is a
conflict that changes nothing. Each successful write increments `edit_version`, which the
transport carries as an ETag. The theme preference shares this version with density,
text size, automation, and AI defaults. On conflict the client preserves its baseline
and local edits, reads the current version, and lets the user explicitly discard or
select local changes to apply over it. Unselected fields retain current server values;
a subsequent save uses that read's ETag. There is no automatic overwrite retry.

The default model and reasoning effort are settings only through their closed
backend-supplied allowlists. Arbitrary model IDs, per-task overrides, timezone, and
secrets are never writable through this command.

## 19b. Maintenance commands

### `reconcile()`

Checks database references and stored artifact hashes against the payload store, and the
fact lifecycle against its audit trail. Both halves always run: a failing artifact check
must not hide a broken lifecycle.

It reports and never repairs. The records it checks are immutable, so a repair would
destroy the evidence of the mismatch. `passed` is the conjunction of both halves; a
failed reconciliation is a successful answer to the question asked, not a command
failure.

### `inspect_orphans()`

`GET /api/v1/maintenance/orphans` returns `candidates`, a sorted list of managed
immutable payload references observed in storage whose group key (architecture.md §7.1)
is absent from the database snapshot **and** holds no live lease row (`pending` or
`reclaiming`). A key still covered by an unexpired lease is never listed - the lease
check is what excludes it. References include JobSnapshots, ApprovedRevision
JSON/Markdown, and every artifact version, including historical and inactive evidence.
Mutable working projections and files outside managed immutable layouts are excluded.

The database read scope closes before storage enumeration. This is a read-only,
non-atomic observation: between this call's several reads, a candidate's lease could be
newly acquired, committed, or reclaimed by other activity. Listing neither changes
reconciliation's `passed` verdict nor deletes anything.

### `reclaim_orphans()`

`POST /api/v1/maintenance/orphans/reclaim` removes two kinds of candidate
`inspect_orphans` would list (architecture.md §7.1 defines both in full):

- One whose group key still holds a `pending` lease, now expired. Reclaim fences it
  first (`pending -> reclaiming`, conditioned on the same attempt_id - the same
  condition a genuine registration needs, so the two serialize against each other), and
  the same update stamps a bounded reclaim deadline on the row. Only after fencing
  succeeds does reclaim check, once more and *before deleting anything*, that the
  database holds no reference to any physical key that attempt produced - a check made
  before deletion because one made only afterward cannot prevent removing a payload
  that turns out to be referenced. A "yes" at this point is an integrity failure, not a
  candidate to skip quietly, and reclaim stops rather than deletes. A "no" allows
  deletion of every physical key the attempt produced, after which the lease row is
  removed last. A second check after deletion may run as additional verification; it is
  not what makes the deletion safe. A group key already found in `reclaiming` past its
  own deadline - a prior call fenced it but stopped before finishing - is resumed, not
  re-fenced: the same reference check, deletion, and lease-row removal repeat, safely,
  since deleting an already-absent key is a no-op (architecture.md §7.1).
- One whose group key holds no lease row at all. No fencing is needed, because a
  missing lease row already makes registration for that key impossible. Reclaim makes
  the same pre-deletion reference check and, finding none, deletes it directly. This is
  the path that removes a key an old attempt's `put` wrote *after* the first case
  already deleted that same attempt's files and lease row on an earlier call - such a
  key can never be registered, so removing it whenever it is next observed is always
  safe.

It guarantees exactly two things: it never removes a payload a database record
references, and it never lets a reclaimed attempt's registration succeed afterward. It
does not guarantee one call removes every orphan, for the reason the second case exists:
an object-store write behind an already-fenced lease is not itself prevented, so it can
still land after that call finished, and only a later call observes it.
`reclaim_orphans` is idempotent and safe to call repeatedly, including concurrently with
itself; operators run it on a schedule rather than once.

## 20. Queries

Initial query contracts include:

- Application list with search/filter/sort and Dashboard projection. Each row carries
  application-owned `is_closed`; the response carries preparation-state, preset, and
  recruitment-status counts computed from the same projected read. Each Dashboard facet
  ignores its own selected value while respecting the other list filters. The list and
  Dashboard exclude deleted Applications (`delete_application`, §12) by default; a
  deleted Application remains reachable at its detail endpoint by ID.
- Application detail with consistent state/action policy and unified timeline
- duplicate candidates for a proposed Application
- active preparation context
- JobSnapshot and analysis history
- SelectionPlan detail and candidate accounting
- WorkingDraft plus ETag
- ValidationRun detail
- ApprovedRevision and Ready qualification detail, plus per-Application immutable revision history
- artifact metadata/download eligibility
- Operation status
- contextual fact detail/history
- submissions and recruitment history
- next-action/overdue projection
- runtime/provider configuration status without secrets
- the allowlisted model catalog, current AI defaults, and immutable execution
  model/reasoning/usage/cost metadata

JobSnapshot history returns the active snapshot ID and all saved snapshots in version
order, with explicit IDs, version numbers, capture times, source URLs, and exact verified
text. Unreadable or unverified text is NULL; history never fetches the live posting,
repairs a payload, or changes the active context. Storage paths are not exposed.

Queries may use direct efficient joins and read models. They return DTOs, not database
rows or local paths.

## 21. HTTP mapping baseline

The API maps each documented command and query to `/api/v1` without adding a second
business contract. Synchronous creation returns `201`; asynchronous commands return
`202` plus an Operation `Location`. The generated OpenAPI document is the authoritative
endpoint inventory. Command sections above remain authoritative for source IDs,
preconditions, idempotency, and synchronous versus asynchronous behavior.

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
