# v2.0 State and Use-Case Contracts

Status: **Approved for v2.0 implementation.** Sections §2–§9, §11, §12, §14–§16, §18–§20
were rewritten for the single-document model
([`../decisions/single-document-model.md`](../decisions/single-document-model.md)).

Product authority: `docs/spec/product-spec.md`

## 1. Purpose

This document defines the detailed lifecycle, state projections, commands, queries,
outcomes, and action policy exposed through the API. It is normative for behavior but
must not override the product specification.

Commands always name the sources they act on. An immutable source is named by ID; the
mutable CVDocument is named by its Application and guarded by the `expected_document_hash`
the client last read. Query/UI conveniences may resolve a latest entity for presentation;
commands may not silently do so.

## 2. Entity lifecycle summary

Mutable:

- Application recruitment projection and safe mutable metadata
- one CVDocument per Application
- one active next action per Application

Immutable or append-only:

- JobSnapshot
- JobAnalysis (one row per analysis; its ID is its identity)
- Submission, including the content and the files it copied
- provider-response Artifact and artifact payload
- recruitment/status/audit events
- completed Operation lifecycle record

What is frozen is what left the system: the posting as captured, the analyses made of it,
the provider responses, and the CV actually sent. Everything else is a working state that
the next command may overwrite. There is no approval history, no draft history, and no
record of a Ready state that was never submitted.

## 3. The CVDocument and its basis

```text
JobSnapshot (immutable)  ->  JobAnalysis (immutable)
                                   |
                                   v
CVDocument (mutable, exactly one per Application once the first analysis activates)
  analysis_id                       the analysis it is pinned to
  selection                         candidates, selected, pinned, excluded, tag coverage,
                                    emphasis, emphasis_override, proposal provenance
  content                           the DraftDocument; NULL until generated
  built_with                        profile_version, selection_policy_version
  document_hash                     stored: hash(analysis_id, selection, content)
  content_report, checked_basis, passed
  approved_basis, approved_at
  rendered_basis, html_path, pdf_path, last_render_error
```

`document_hash` is the SHA-256 of the canonical JSON of `analysis_id`, `selection` and
`content`. It is rewritten by every command that changes one of them and by nothing else.
It is also the document's concurrency token: every command that changes the document
carries `expected_document_hash`, and a mismatch is a conflict that writes nothing. Two
states with the same hash are the same document, so a change computed against one is
valid against the other.

`facts_hash` is the SHA-256 of the canonical JSON of the current state of every fact the
document depends on: the fact IDs in `selection` united with the fact IDs cited by the
claims in `content`. Each entry carries the fact ID, its lifecycle status, and its
canonical content; a fact that no longer resolves is entered as missing. `facts_hash` is
computed on read from the loaded Knowledge and never stored.

```text
basis = hash(document_hash, facts_hash)
```

The basis is computed on read. Only three stamps of it are stored:

- `checked_basis`: the basis the stored `content_report` was produced for;
- `approved_basis`: the basis that was approved;
- `rendered_basis`: the basis whose files `html_path`/`pdf_path` hold.

A NULL stamp never equals the basis. Any change to the document, or to a fact it depends
on, changes the basis, however the fact changed — through the Knowledge mutation journal
or by hand in `base/`. No command invalidates a stamp by writing: an outdated stamp simply
no longer equals the basis on the next read.

The document is pinned to its analysis:

- The first activated analysis of an Application, when no document exists, creates the
  document with that analysis's deterministic selection and no content. Creation relies
  on the one-document-per-Application unique constraint.
- A later analysis never changes the document. It raises `DOCUMENT_ON_OLDER_ANALYSIS`
  (§8).
- `build_from_analysis` (§14) is the explicit action that re-pins the document.

## 4. PreparationState

Values:

```text
needs_analysis
ready_to_draft
draft_in_progress
approved
ready
```

Projection rules, first match wins, over inputs captured in one consistent database
snapshot (§9):

1. No CVDocument exists -> `needs_analysis`.
2. `content IS NULL` -> `ready_to_draft`.
3. `rendered_basis == approved_basis == basis` -> `ready`.
4. `approved_basis == basis` -> `approved`.
5. Otherwise -> `draft_in_progress`.

A review reason (§7) is an overlay on these states, not a state: it blocks the actions it
names and leaves the PreparationState as projected. Ready and approved are therefore never
hidden by unrelated work, and they are lost only by a change the basis covers.

A newer JobSnapshot or JobAnalysis does not change the PreparationState of an existing
document. It is reported by the `DOCUMENT_ON_OLDER_ANALYSIS` warning, and `analyze` and
`build_from_analysis` are offered according to §9.

## 5. DocumentState and content check

`document_state` restates the approval stamps on their own:

```text
none        no CVDocument
draft       approved_basis IS NULL OR approved_basis != basis
approved    approved_basis == basis AND (rendered_basis IS NULL OR rendered_basis != basis)
ready       rendered_basis == approved_basis == basis
```

`content_check` describes the stored content report:

```text
none        no report has been produced, or content IS NULL
outdated    checked_basis != basis
failed      checked_basis == basis AND passed = false
passed      checked_basis == basis AND passed = true
```

An outdated report is still returned so the client can show it as outdated; it never
authorizes anything. An ETag conflict is a save-attempt outcome held by the client until
resolution, not a persisted state.

## 6. Why nothing goes stale

The revision model froze a context and reported `stale` reasons when a source moved. The
document model has no frozen context to go stale:

- A document edit, a selection change, or a re-pin changes `document_hash`, so every
  stamp is outdated at once.
- A fact edit, replacement, demotion, or deletion that the document depends on changes
  `facts_hash`, so every stamp is outdated at once. An unrelated fact change does not.
- A newer analysis or snapshot is a warning (`DOCUMENT_ON_OLDER_ANALYSIS`); the document
  stays as it was until `build_from_analysis`.
- A profile or selection-policy change is a warning (`PROFILE_CHANGED`,
  `POLICY_CHANGED`) derived from `built_with` against the current versions. Approval and
  rendering validate against the current values, so the warning never lets an outdated
  build through.

There is no `stale_reasons` projection and no `primary_stale_reason`.

## 7. Review reasons

Review reasons are blockers that require an explicit user decision. Codes:

```text
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

`PENDING_FACT_REQUIRES_RESOLUTION` and `FACT_DELETED_REQUIRES_RESOLUTION` are computed
over the same fact set as `facts_hash` — the document's selection united with the facts
its claims cite — plus a requested selection. A pending or deleted fact outside that set
does not affect the Application. `FACT_DELETED_REQUIRES_RESOLUTION` refers to
`FactStatus.DELETED` (§17).

A review reason blocks `approve` and `render`, and therefore Ready and `submit`. It does
not block editing, selection changes, generation, or regeneration: those are how it is
resolved.

Each reason includes a safe message, relevant entity references, and allowed resolution
action identifiers.

## 8. Warnings, blockers, and failures

- A warning is important but does not disable approval.
- A blocker disables one or more commands.
- A review reason is a blocker requiring explicit human judgment.
- An error is a technical or Operation failure rather than domain state.

Warning codes:

```text
DOCUMENT_ON_OLDER_ANALYSIS
PROFILE_CHANGED
POLICY_CHANGED
FACT_SUPERSEDED
FACT_KNOWN_INCORRECT
NEXT_ACTION_OVERDUE
```

`DOCUMENT_ON_OLDER_ANALYSIS` applies when the document's `analysis_id` is not the newest
JobAnalysis of the Application, or when the document's analysis was made of a JobSnapshot
other than the active one. It replaces the revision model's snapshot, analysis and
selection-plan replacement reasons.

`FACT_SUPERSEDED` and `FACT_KNOWN_INCORRECT` are computed over the `facts_hash` fact set.
`FACT_KNOWN_INCORRECT` is materially stronger than supersession. Neither rewrites a
Submission, which is immutable and keeps the content it sent.

A deleted fact the document still depends on is the `FACT_DELETED_REQUIRES_RESOLUTION`
blocker (§7), never a warning.

## 9. Action policy projection

Application Detail and relevant list projections return:

```json
{
  "recruitment_status": "saved",
  "terminal_outcome": null,
  "preparation_state": "draft_in_progress",
  "document_state": "draft",
  "content_check": "failed",
  "review_reasons": [],
  "warnings": [],
  "active_operation": null,
  "latest_operation": null,
  "active_job_snapshot_id": "...",
  "latest_analysis_id": "...",
  "document_id": "...",
  "document_hash": "...",
  "document_analysis_id": "...",
  "approved_at": null,
  "last_render_error": null,
  "available_actions": ["check", "regenerate_claim"],
  "blocked_actions": [
    {"action": "approve", "reasons": ["VALIDATION_FAILED"]}
  ],
  "recommended_action": "check"
}
```

All database inputs, including the Knowledge the basis is computed from, are captured in
one read. The projection is derived from that capture. `recommended_action` is
deterministic and nullable. Action identifiers are stable application commands, not UI
labels.

Action availability:

| Action | Available when |
| --- | --- |
| `analyze` | the active JobSnapshot has no JobAnalysis, and no `analyze_job` is queued/running |
| `edit_matching_configuration` | a JobAnalysis exists and no queued/running Operation can replace it or change the document selection |
| `build_from_analysis` | a document exists and a newer JobAnalysis than `document_analysis_id` exists |
| `update_selection`, `propose_selection` | a document exists |
| `create_draft` | a document exists and `content IS NULL` |
| `edit`, `regenerate_section`, `regenerate_claim` | `content IS NOT NULL` |
| `check` | `content IS NOT NULL` and `content_check != passed` |
| `approve` | `content IS NOT NULL`, `document_state = draft`, and no review reason |
| `render` | `document_state = approved` and no review reason |
| `submit` | `document_state = ready` and no review reason |
| `download_pdf` | `document_state = ready` |

A queued or running Operation that mutates the document disables every other command
that mutates it. `edit_matching_configuration` means voluntarily editing the matching
context; it is committed through the `apply_analysis_decisions` backend endpoint, which
is an implementation name, not a separate advertised action.

Recommendation order, first match wins: `analyze` when no document exists; `create_draft`
when content is NULL; `check` when the report is not current; `approve`; `render`;
`submit`; otherwise null.

`active_operation` is limited to queued/running work and is the polling and concurrency
signal. `latest_operation` is the newest lifecycle record whether live or terminal, so a
failed outcome remains presentable after active work ends. A live Operation may therefore
appear in both fields; clients prefer `active_operation` while work is in flight.

`last_render_error` is the structured failure of the newest failed render whose expected
document hash still equals `document_hash` (§16). It is cleared by a successful render and
is not shown once the document has changed.

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

Operation types:

```text
analyze_job
propose_selection
create_draft
regenerate_section
regenerate_claim
render_document
```

Manual edits, deterministic selection changes, `build_from_analysis`, `check`, `approve`
and `submit` are synchronous and are never Operations.

An Operation that mutates an existing document (`propose_selection`, `create_draft`,
`regenerate_section`, `regenerate_claim`, `render_document`) carries
`expected_document_hash`. At activation it locks the document row; a mismatch discards
the result and fails the Operation with `SOURCE_CHANGED`. `analyze_job` is bound to its
input JobSnapshot, not to a document. Operations keep the input identities they need to
execute, retry and pin, but draft-producing Operations do not recheck input freshness at
activation: their output is unapproved, and `approve`/`render` validate against the
current authoritative context (facts and their eligibility, profile, policy, evidence).

Failure reason is separate. Stable failure codes:

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
terminal.

`CLAIM_REVIEW_UNCERTAIN` means the semantic reviewer could not establish that a
proposed paraphrase is supported. `CLAIM_REVIEW_UNSUPPORTED` means it found that the
proposal exceeds or contradicts the cited canonical facts. Both are terminal and leave
the document unchanged; malformed or incomplete reviewer output remains
`INVALID_OUTPUT`.

An Operation may be failed/cancelled while owning an inactive immutable output (provider
evidence). Output existence and output activation are separate.

Operation query fields include status, phase, message, timestamps, failure code, safe
failure detail, structured failure reason, retry reference, cancellation state, output
references, and the backend-derived Operation actions currently accepted. The UI polls every one to two
seconds. It does not display fabricated percentages or re-derive lifecycle permissions
from status strings.

The structured failure reason is the failure's cause in a closed vocabulary with typed
parameters - a PDF page count against its limit, a fact missing a rendering in a language,
a named render check - written when the failure is recorded. The safe failure detail is
the same cause as an English sentence; a client explains the failure from the reason and
never parses the sentence. The reason is null when the code alone says everything.

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
snapshot and makes it the active snapshot. It does not mutate or delete older snapshots
or analyses, and it does not change the document.

### `close_application`

Transitions a saved/non-terminal Application through the allowed policy to `closed`.
There is no hard-delete command in the Web UI.

### `delete_application(application_id)`

Soft-deletes an Application: sets a terminal `deleted_at` disposition and appends an
audit event. It is orthogonal to `RecruitmentStatus` — available from any status
including `closed` — and does not itself transition `current_status`. A deleted
Application is excluded from default list/dashboard/search projections and from
duplicate detection, but its record, its document, and every immutable JobSnapshot,
JobAnalysis, Artifact, Submission, and Operation it produced remain unchanged and
individually reachable by ID. There is no hard delete and no `undelete` command in this
phase; a mistaken deletion is corrected the same way a mistaken status is, by explicit
reason, not by reversing the flag. Calling it on an Application already deleted is
refused with `StateConflict` (409) — the same idempotency posture as `delete_fact`
refusing an already-`deleted` fact — rather than silently succeeding again or appending a
second `delete_application` audit event.

Every command in §13–§16 and `submit_application` (§18) resolves its Application through
one shared precondition rather than each service repeating its own check: 404 if the
Application does not exist, 409 (`StateConflict`) if it is deleted, otherwise the record.
A read that must still resolve a deleted Application's history on purpose — the
detail-by-ID projection, submission detail, `export_decision_markdown` — is exempt by
design, exactly as §17's `show_fact` stays exempt for a deleted fact.

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
Legacy concept/rule gaps are not unioned into or allowed to veto this result.

Every successful activation creates one immutable JobAnalysis. When the Application has
no document, the same transaction creates the CVDocument pinned to that analysis, with
the analysis's deterministic selection, `built_with` set to the current profile and
selection-policy versions, and no content. When a document exists, activation does not
touch it. The result returns the analysis ID, the document ID, and the projected state.

Preconditions:

- snapshot belongs to Application
- a configured provider is available

For AI mode, the application resolves the current allowlisted model and reasoning
preference before writing the Operation. Those values are part of the immutable payload
and runner record; the worker never re-reads Settings to decide what to execute.

### `apply_analysis_decisions`

Synchronous. It accepts one local form submission naming the analysis it addresses
(`expected_analysis_id`) and, when a document exists, `expected_document_hash`. Under the
Application write lock both must still match; a mismatch returns a conflict and writes
nothing. The same transaction refuses the decision while a queued or running Operation
can replace the analysis or change the document selection. Operation admission and this
check serialize on the same Application lock.

- A change to requirement meaning or to the Track/Profile/language classification
  creates one new immutable JobAnalysis. It never mutates the original. The document is
  not changed; the new analysis raises `DOCUMENT_ON_OLDER_ANALYSIS` until the user runs
  `build_from_analysis`. When no document exists, the new analysis creates it as in
  `analyze_job`.
- An Emphasis decision or a fact-selection decision on the document's own analysis
  updates the document selection in place, exactly as `update_selection` does, including
  its effect on content.
- An Emphasis decision accompanying a classification change is carried into the new
  analysis's deterministic selection.

A *fact* overlay may not accompany a classification change: pinned and excluded facts are
decided against candidate accounting the new analysis has not produced yet, so they stay
a second command.

After a successful commit the API response includes the newly computed application-state
projection, including `available_actions` and `recommended_action`. The Web client chooses
the next step from that projection and does not predict it from the submitted fields.

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

## 14. Document commands

### Wording evidence contract

The following rules govern generation, regeneration, editing, checking, and approval.
Canonical/extractive/presentation proof or complete eligible reviewed evidence under
product-spec §10.1 may establish claim support. Positive reviewed evidence needs no
individual user confirmation. Uncertainty cannot be downgraded to a warning; known
contradiction or unsupported content cannot be overridden by general approval.

Review execution uses persisted Operations and `expected_document_hash`. A provider
result with uncertainty is a domain review outcome, not a transport failure, and does
not authorize activation as supported content. Unsupported AI wording remains refused;
unsupported manual text remains savable as pending/unlinked. Evidence cannot be
activated after cancellation or against a changed document.

A missing review or unresolved clarification blocks approval through both action policy
and application services. Claim-level evidence may remain reusable after an unrelated
edit only when its actual dependencies still match. The v1 writer/reviewer flow adds no
public command or PreparationState value. Its provider DTOs carry the exact proposed
claims, section context, linked fact IDs, allowed canonical sources, and one ordered
assertion/source-quote mapping per reviewed claim. Only a fully supported result
activates. Uncertain/unsupported results fail the existing Operation with immutable
inactive provider evidence and leave the document unchanged.

### `update_selection(application_id, expected_document_hash, change)`

Synchronous and deterministic. Selects, pins, excludes, or unselects facts, or sets the
Emphasis override, on the document's selection. It validates Profile/Track/Emphasis and
allowed-fact constraints against the document's analysis and the current Knowledge.

When `content IS NULL`, only the selection changes. When content exists, the command
updates selection and content atomically when the change is deterministic and
unambiguous; a change that requires wording judgment returns an outcome directing the
client to a regeneration command and writes nothing. The selection records its effective
`emphasis` separately from the nullable `emphasis_override`.

### `propose_selection(application_id, expected_document_hash, provider)`

Asynchronous, idempotent AI Operation. The provider output is only a Proposal;
activation repeats the deterministic validations of `update_selection` and the
`expected_document_hash` check before replacing the selection. It is available only while
`content IS NULL`. A selection activated from a Proposal records `proposed_by = "ai"` and
the provider's written rationale inside the selection. They are provenance only:
activation never reads them. Engine and user selections leave both null. No provider call
occurs inside a synchronous HTTP request.

### `build_from_analysis(application_id, analysis_id, expected_document_hash)`

Synchronous and deterministic. Re-pins the document to an explicitly named JobAnalysis of
the same Application: it replaces `analysis_id`, sets the selection to that analysis's
deterministic selection, refreshes `built_with`, and sets `content` to NULL. The same
write clears the content report and all three stamps, and clears `html_path`,
`pdf_path` and `last_render_error`; the previous rendered files are deleted best-effort
after commit. It is the only command that changes `analysis_id`.

### `create_draft(application_id, expected_document_hash, provider)`

Asynchronous and idempotent. The deterministic path constructs the canonical
DraftDocument from the document's analysis and selection. AI mode uses the `draft_resume`
Proposal and semantic validation. Activation writes `content` only while
`document_hash == expected_document_hash`.

AI selection proposals, draft generation, and targeted regeneration freeze the same
model/reasoning pair at submission. Retry copies that pair from the original Operation.

### `update_document(application_id, expected_document_hash, patch)`

Synchronous autosave command. The input is a structured content patch. It returns the
new `document_hash`. A mismatch returns Conflict and changes nothing.

Free-text is saved as pending/unlinked when it cannot be authorized. It is not silently
rejected or discarded.

### `regenerate_section` / `regenerate_claim`

Asynchronous, idempotent AI Operations. They receive the Application, the
`expected_document_hash`, the target section/claim, and minimal facts/policies. Output is
a Proposal; activation uses the same `expected_document_hash` rule as `create_draft`.

Editing an approved or ready document is allowed. It changes the basis, so the document
returns to `draft` on the next read; no command reopens it.

## 15. Check and approval commands

### `check_document(application_id, expected_document_hash)`

Synchronous deterministic content validation. It does not call a provider. It runs the
validation contract against the current content, the document's analysis and selection,
and the current Knowledge, profile, policy and evidence, and stores the result in one
write: `content_report`, `passed`, and `checked_basis` set to the basis the check ran
against. It always stores the report when validation executed, including `passed=false`.
Validator execution failure is an application/infrastructure error and stores nothing.

The report records its issues, groups and evidence, and the validator versions. For
reviewed wording, evidence includes exact review/proof references. Validation checks
hard-rule results, full assertion coverage, permitted evidence kind, no unresolved
contradiction/uncertainty, and that every claim's facts are eligible. It does not infer
success from a missing review.

### `approve_document(application_id, expected_document_hash)`

Synchronous. It runs `check_document`'s validation and approves in one action, under the
document row lock:

- It always stores the report and `checked_basis`.
- It sets `approved_basis` to the checked basis and `approved_at` only when the report
  passed and no review reason or blocker exists.
- When `approved_basis` already equals the basis it returns the existing approval: it
  does not rewrite `approved_at` and appends no audit record.

A failed check is returned as data (`200` with the report), not as an exception. A review
reason or other blocker is refused with a precondition failure naming it.

A no-pause flow (product-spec.md §11) is an explicit user approval action here too: it
may orchestrate check -> approve -> render with `actor_type=user` and the originating
client, but it is subject to every validation, warning confirmation, and blocker rule
above.

Warnings may require one general confirmation. No warning that actually requires a
specific resolution may reach this command as a warning.

## 16. Rendering commands

### `render_document(application_id, expected_document_hash)`

Asynchronous and idempotent. Admission requires `document_state = approved` and no
review reason. The Operation validates the content, writes HTML and renders PDF with
Playwright Chromium to a unique per-attempt path, and checks geometry, page count,
PDF/ATS text, links, direction, and filename metadata. All rendering happens outside
database scopes.

Activation locks the document row and requires `approved_basis == basis` and
`document_hash == expected_document_hash`. Only then does it swap `html_path` and
`pdf_path` to the new files, stamp `rendered_basis`, and clear `last_render_error`.
Render activation is the only writer of `rendered_basis`.

A failure records `last_render_error` (structured failure reason) only while
`document_hash` still equals the expected hash; otherwise only the Operation keeps the
failure. A failure never touches the active files or `rendered_basis`. Superseded files
(after success) and failed-attempt files are deleted best-effort. Readiness does not
depend on a render version, and no render output is registered as an Artifact.

After a render failure the document stays approved. Correction is an ordinary edit,
which returns the document to draft; retry creates a new Operation.

### `export_recruiter_pdf(application_id)`

Synchronous read. It computes the basis at request time and refuses unless
`document_state = ready`. It verifies path containment and that the file exists before
returning it with a friendly Content-Disposition filename.

### `export_decision_markdown(application_id)`

Produces a human-readable provenance export of the current document: its analysis,
selection, the facts it depends on, and the stored content report. It writes nothing.
Diagnostic JSON remains available through the API but is not the primary human export.

## 17. Knowledge commands

### `list_facts(status=None)` / `show_fact(fact_id)` / `fact_history(fact_id=None)`

Synchronous reads over the candidate Fact pool and its immutable lifecycle events.
`list_facts` may filter by lifecycle status; with no filter it excludes `deleted` facts,
which remain reachable by an explicit `status=deleted` filter or by `show_fact`.
`show_fact` returns one fact with its events. The dedicated candidate-facts surface uses
these reads without requiring an Application, JobAnalysis, or document context.

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
attestation. Promoting a replacement makes the original fact superseded for warning
purposes; it does not rewrite or remove the original record or any Submission.

### `delete_fact(fact_id)`

Moves a fact from `pending`, `confirmed`, or `canonical` to the terminal `deleted`
status. Refuses a fact already `deleted`. It is a soft delete through the same
Knowledge mutation journal as every other transition: the fact record and its full
lifecycle history are preserved and remain reachable via `show_fact`/`fact_history`,
but a deleted fact is excluded from `list_facts` by default, from
`list_fact_attachment_targets` results, and is refused by `confirm_fact`,
`promote_fact`, `attach_fact`, and `confirm_and_use_fact`.

Deletion is always permitted, including for a fact currently attached to a Profile
section or used by a document — it does not require detaching first, and it writes
nothing to any document. A document that depends on the deleted fact sees its basis
change and reports `FACT_DELETED_REQUIRES_RESOLUTION` (§7) until the dependency is
resolved (re-selection, edit, or replacement fact). A Submission that already carries
the fact is immutable and unaffected. Deletion never rewrites, removes, or reassigns the
fact's canonical content, and it is a separate disposition from `replaces`-based
canonical correction: deleting a fact does not create a replacement, and creating a
replacement does not delete the original.

### `attach_fact(fact_id, profile, section, pin=False)`

Offers one canonical fact to an explicitly named existing Profile section. It may pin the
fact within that section. It does not edit Profile structure or change any document
selection. Non-canonical facts are refused.

### `confirm_and_use_fact`

One logical cross-store command:

```text
pending -> confirmed -> canonical
-> attach to explicit Profile section
-> select the fact in the named Application's document (update_selection)
```

Every transition receives a separate audit event. Complete validation occurs before
mutation, the journal provides deterministic recovery, and normal queries never expose
partial completion. A failure reports the whole command as unsuccessful. The journal's
selection step is a document selection update guarded by `expected_document_hash`.

### `create_fact_from_claim`

Copies exact claim text into the appropriate rendering without AI rewrite. Meaning,
tags, provenance, and other required metadata are supplied explicitly. It creates a
pending fact and does not authorize the claim until the lifecycle/attachment/selection
is complete.

Canonical correction creates a replacement fact carrying `replaces`; it never mutates
the old fact content.

`delete_fact` (above) is the only removal command in this lifecycle. Archive,
withdrawal, retirement, and distinct `known-incorrect` transitions remain undefined:
adding them requires a separate contract for their effects on Profile pools, selection,
warnings, validation, reconciliation, and Submissions. Their absence must not be
presented by a client as an available action.

## 18. Tracking commands

### `submit_application(application_id, expected_document_hash, submitted_at, metadata)`

Records a send that already happened; it carries the submission time. It is not a
validation gate. Under the document row lock it requires
`rendered_basis == approved_basis == basis` and `document_hash == expected_document_hash`
and no review reason. It copies the content and the rendered HTML and PDF to
submission-owned paths under a payload write lease, computing a SHA-256 per file, and
then, in one PostgreSQL transaction, inserts the immutable Submission, transitions to
`applied` if required, and appends status/audit events.

An internal Submission records:

- the content it sent and its `document_hash`;
- the `job_snapshot_id` of the document's analysis (FK `RESTRICT`);
- `html_path` + `html_sha256` and `pdf_path` + `pdf_sha256`.

When the active snapshot or analysis is newer than the document's, the outcome includes
the `DOCUMENT_ON_OLDER_ANALYSIS` warning; it is not a precondition.

Multiple submissions are allowed. Later submissions do not add a redundant `applied`
transition or reset recruitment state. Submitting does not change the document.

### `record_external_submission`

Records an immutable external submission that carries no document content or files. It
transitions to `applied` if required and records explicit provenance.

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
Operation remains immutable. Reusing the old key returns the old result. A retry of a
document-mutating Operation carries the current `document_hash` as its
`expected_document_hash`.

`MISSING_FACT_RENDERING` and `SOURCE_CHANGED` are not retryable. A missing rendering
requires a changed Fact or selection, while a source change requires a new command
against the current document. In both cases the Operation exposes no `retry` action.

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

Checks database references and stored hashes against the payload store — JobSnapshot
payloads, provider-response artifact versions, and every Submission file against its
SHA-256 — and the fact lifecycle against its audit trail. Both halves always run: a
failing artifact check must not hide a broken lifecycle.

It reports and never repairs. The records it checks are immutable, so a repair would
destroy the evidence of the mismatch. `passed` is the conjunction of both halves; a
failed reconciliation is a successful answer to the question asked, not a command
failure. The document's rendered files are mutable working outputs and are not checked.

### `inspect_orphans()`

`GET /api/v1/maintenance/orphans` returns `candidates`, a sorted list of managed
immutable payload references observed in storage whose group key (architecture.md §7.1)
is absent from the database snapshot **and** holds no live lease row (`pending` or
`reclaiming`). A key still covered by an unexpired lease is never listed - the lease
check is what excludes it. References include JobSnapshots, Submission files, and every
provider-response artifact version, including inactive evidence. The document's rendered
files and files outside managed immutable layouts are excluded.

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

Query contracts:

- Application list with search/filter/sort and Dashboard projection. Each row carries
  application-owned `is_closed`; the response carries preparation-state, preset, and
  recruitment-status counts computed from the same projected read. Each Dashboard facet
  ignores its own selected value while respecting the other list filters. The list and
  Dashboard exclude deleted Applications (`delete_application`, §12) by default; a
  deleted Application remains reachable at its detail endpoint by ID.
- Application detail with consistent state/action policy and unified timeline
- duplicate candidates for a proposed Application
- JobSnapshot and analysis history
- the CVDocument: analysis ID, selection with candidate accounting, content,
  `built_with`, `document_hash` (carried as the ETag), the content report with its
  `content_check`, `document_state`, `approved_at`, and `last_render_error`
- Operation status
- contextual fact detail/history
- submissions (with their content and file metadata) and recruitment history
- next-action/overdue projection
- runtime/provider configuration status without secrets
- the allowlisted model catalog, current AI defaults, and immutable execution
  model/reasoning/usage/cost metadata

JobSnapshot history returns the active snapshot ID and all saved snapshots in version
order, with explicit IDs, version numbers, capture times, source URLs, and exact verified
text. Unreadable or unverified text is NULL; history never fetches the live posting,
repairs a payload, or changes the active context. Storage paths are not exposed.

There is no revision history and no revision comparison. The history of what was sent is
the list of Submissions.

Queries may use direct efficient joins and read models. They return DTOs, not database
rows or local paths.

## 21. HTTP mapping baseline

The API maps each documented command and query to `/api/v1` without adding a second
business contract. Synchronous creation returns `201`; asynchronous commands return
`202` plus an Operation `Location`. The generated OpenAPI document is the authoritative
endpoint inventory. Command sections above remain authoritative for source IDs,
preconditions, idempotency, and synchronous versus asynchronous behavior.

The document is read and written at the Application's document resource. Its
`document_hash` travels as the ETag; commands that take `expected_document_hash` accept
it as `If-Match`.

## 22. HTTP outcomes

- `200`: query/update or successful outcome such as a failed content check
- `201`: synchronous entity creation
- `202`: accepted Operation with `Location`
- `409`: optimistic concurrency (`expected_document_hash` mismatch) or idempotency-key
  payload mismatch
- `412`: missing domain precondition or blocker
- `413`: body limit exceeded
- `422`: invalid request schema
- `500/503`: infrastructure execution failure as appropriate

Problem Details carries stable `code`, safe `detail`, and safe `context`. Examples:

```text
DOCUMENT_CHANGED
DOCUMENT_NOT_APPROVED
DOCUMENT_NOT_READY
VALIDATION_FAILED
UNLINKED_CLAIM
IDEMPOTENCY_KEY_REUSED
SOURCE_CHANGED
KNOWLEDGE_RECONCILIATION_REQUIRED
```

Review reasons and domain validation issues are data, not exceptions.
