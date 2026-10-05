# State and Use-Case Contracts

Status: **Binding.** Describes the single-document model as implemented
([`../decisions/single-document-model.md`](../decisions/single-document-model.md)).
Accounts and per-user isolation (§23, product-spec.md §22) are approved and not built;
each rule they change is marked *designed, not built*.

Product authority: [`product-spec.md`](product-spec.md). Section numbers are cited from
code docstrings; keep them stable.

## 1. Purpose

This document defines state values, their projections, the commands and queries the
application layer exposes, their preconditions and outcomes, and the action policy the
API returns. It is normative for behavior and does not override the product
specification.

Commands name the sources they act on. An immutable source is named by ID. The mutable
CVDocument is named by its Application and guarded by the `expected_document_hash` the
client last read. A query may resolve "latest" for presentation; a command never does.

Every write records `actor_type` (`user` | `system`) and `client` (`web` | `worker`).
*Designed, not built (§23):* every command and query runs for one signed-in user and
reaches only that user's records; the acting user is the owner of what it touches, and
the worker acts for the owner of the Operation. Today there is no authenticated user.

## 2. Entity lifecycle summary

Mutable:

- the Application: recruitment status, terminal outcome, notes, next action, and the
  `deleted_at` disposition
- exactly one CVDocument per Application, once the first analysis activates
- the active JobSnapshot pointer
- the Settings row (one per user once accounts ship)
- *designed, not built (§23):* the user, their sessions, and their facts' current status

Immutable or append-only:

- JobSnapshot and its payload
- JobAnalysis (one row per analysis; its ID is its identity)
- Submission, including the content it sent and the files it copied
- the AI call log: one row per provider call attempt, with its sanitized response
- recruitment, status, audit, and fact lifecycle events
- *designed, not built (§23):* account events
- a terminal Operation record

What is frozen is what left the system or what was observed: the posting as captured,
the analyses made of it, provider responses, and the CV actually sent. Everything else
is working state the next command may overwrite. There is no approval history, no draft
history, and no record of a Ready state that was never submitted.

## 3. The CVDocument and its basis

```text
JobSnapshot (immutable)  ->  JobAnalysis (immutable)
                                   |
                                   v
CVDocument (mutable, one per Application)
  analysis_id                       the analysis it is pinned to
  content                           the DraftDocument; NULL until generated
  built_with                        profile_version
  document_hash                     stored: hash(analysis_id, content)
  content_report, passed, checked_basis
  approved_basis, approved_at
  rendered_basis, html_path, pdf_path, last_render_error
```

`document_hash` is the SHA-256 of the canonical JSON of `analysis_id` and `content`. Every command that changes one of them rewrites it; nothing else does. It is
the document's concurrency token: a command that changes the document carries
`expected_document_hash`, and a mismatch is `DOCUMENT_CHANGED` (409) with nothing
written.

The **dependent fact set** is every fact ID cited by the headline, contact, and section
claims in `content`; it is empty while `content IS NULL`. The document holds no separate
selection: the facts it uses are the facts its content links
(`docs/decisions/ai-owned-selection.md`).

`facts_hash` is the SHA-256 of the canonical JSON of
each dependent fact's full current record (status included, storage location excluded),
sorted by ID; a fact that no longer resolves is entered as missing. It is computed on
read and never stored.

```text
basis = sha256(document_hash + ":" + facts_hash)
```

The basis is computed on read. Three stamps of it are stored:

- `checked_basis`: the basis `content_report` was produced for;
- `approved_basis`: the basis that was approved;
- `rendered_basis`: the basis whose files `html_path`/`pdf_path` hold.

A NULL stamp never equals the basis. Any change to the document, or to a dependent fact,
changes the basis however the fact changed — through the Knowledge mutation journal or
by hand in `base/`. No command invalidates a stamp by writing; an outdated stamp simply
no longer matches on the next read.

Pinning:

- The first activated analysis of an Application creates the document pinned to it with
  no content, relying on the
  one-document-per-Application unique constraint.
- A later analysis never touches the document; it raises `DOCUMENT_ON_OLDER_ANALYSIS`
  (§8).
- `build_from_analysis` (§14) is the only command that changes `analysis_id`.

## 4. PreparationState

```text
needs_analysis
ready_to_draft
draft_in_progress
approved
ready
```

First match wins, over one consistent read (§9):

1. No CVDocument -> `needs_analysis`.
2. `content IS NULL` -> `ready_to_draft`.
3. `approved_basis == basis AND rendered_basis == basis` -> `ready`.
4. `approved_basis == basis` -> `approved`.
5. Otherwise -> `draft_in_progress`.

PreparationState is the one document state the API and UI read. "Approved" and "Ready"
in this document mean `preparation_state` `approved` and `ready`. The domain keeps its
own restatement of the approval stamps (`DocumentState`) for the commands that check
them; it is not exposed.

A review reason (§7) is an overlay: it blocks the actions it names and leaves the
PreparationState as projected. A newer JobSnapshot or JobAnalysis does not change the
PreparationState of an existing document; it is reported by the
`DOCUMENT_ON_OLDER_ANALYSIS` warning.

## 5. Content check

`content_check` describes the stored content report:

```text
none        no document, content IS NULL, or checked_basis IS NULL
outdated    checked_basis != basis
failed      checked_basis == basis AND passed = false
passed      checked_basis == basis AND passed = true
```

An outdated report is still returned so the client can show it as outdated; it never
authorizes anything. An ETag conflict is a save-attempt outcome the client holds until
resolved, not persisted state.

## 6. Why nothing goes stale

There is no frozen context and no `stale_reasons` projection:

- A content edit or re-pin changes `document_hash`, so every stamp is
  outdated at once.
- A change to a dependent fact (edit, status transition, replacement, deletion, removal
  from `base/`) changes `facts_hash`, so every stamp is outdated at once. A change to an
  unrelated fact does not.
- A newer analysis or snapshot is the `DOCUMENT_ON_OLDER_ANALYSIS` warning; the document
  stays as it is until `build_from_analysis`.
- A Profile version change is the `PROFILE_CHANGED` warning, derived from
  `built_with`. Approval and rendering validate
  against the current Knowledge, so the warning never lets an outdated build through.

## 7. Review reasons

Review reasons are blockers that need an explicit user decision. They are computed over
the dependent fact set (§3):

```text
PENDING_FACT_REQUIRES_RESOLUTION     a dependent fact is pending
FACT_DELETED_REQUIRES_RESOLUTION     a dependent fact has status deleted
```

A pending or deleted fact outside that set does not affect the Application. Each reason
carries a safe message, entity references (`document_id` and the first offending
`fact_id`), and its resolution actions:

| Reason | Resolution actions |
| --- | --- |
| `PENDING_FACT_REQUIRES_RESOLUTION` | `confirm_and_use_fact`, `edit` |
| `FACT_DELETED_REQUIRES_RESOLUTION` | `edit`, `regenerate_section`, `regenerate_claim` |

A review reason blocks `approve`, `render` and `submit`, which refuse with a 412 whose
`code` is the first reason. It does not block editing, generation, or regeneration: those are how it is resolved.

Analysis issues, low Fit, and hard gaps are diagnostics, not review reasons. They stay
visible and block nothing. Missing evidence is not evidence of missing experience: an
uncertain requirement stays `unknown`.

`KNOWLEDGE_RECONCILIATION_REQUIRED` is not projected as a review reason. It is the
refusal `approve_document` returns while any Knowledge mutation is quarantined (§15).

## 8. Warnings, blockers, and failures

- A warning is shown but disables nothing.
- A blocker disables one or more actions (`blocked_actions`, §9).
- A review reason is a blocker that needs human judgment (§7).
- An error is a refusal or an Operation failure, not domain state.

Warning codes:

```text
DOCUMENT_ON_OLDER_ANALYSIS
PROFILE_CHANGED
FACT_SUPERSEDED
NEXT_ACTION_OVERDUE
```

- `DOCUMENT_ON_OLDER_ANALYSIS`: the document's `analysis_id` is not the newest
  JobAnalysis of the Application, or its analysis was made of a JobSnapshot other than
  the active one.
- `PROFILE_CHANGED`: `built_with` differs from the current Profile version.
- `FACT_SUPERSEDED`: a canonical fact `replaces` a dependent fact. It never rewrites a
  Submission.
- `NEXT_ACTION_OVERDUE`: `next_action_date` is before today and the recruitment status
  is not `accepted`, `rejected`, `withdrawn`, or `closed`.

A deleted dependent fact is the `FACT_DELETED_REQUIRES_RESOLUTION` blocker, never a
warning. There is no known-incorrect fact status and no warning for one.

## 9. Action policy projection

Application detail and every list row return:

```json
{
  "recruitment_status": "saved",
  "terminal_outcome": null,
  "preparation_state": "draft_in_progress",
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
  "available_actions": ["edit", "regenerate_section", "regenerate_claim", "check"],
  "blocked_actions": [{"action": "approve", "reasons": ["VALIDATION_FAILED"]}],
  "recommended_action": "check"
}
```

All inputs — the Application, snapshots, analyses, document, Operations, and the
Knowledge the basis is computed from — are captured in one read, and the projection is
derived from that capture. Action identifiers are stable command names, not UI labels.
Detail additionally returns `allowed_recruitment_transitions` (§10), the latest
snapshot and analysis, and the recruitment timeline.

- `approved_at` is reported only while `preparation_state` is `approved` or `ready`.
- `last_render_error` is reported only while its recorded hash equals `document_hash`
  (§16).
- `active_operation` is the queued/running Operation, if any; it is the polling and
  concurrency signal. `latest_operation` is the newest Operation whether live or
  terminal, so a failure stays presentable after work ends.

Each action is first allowed or not by the stage. An action the stage does not allow
appears in neither `available_actions` nor `blocked_actions`: the stage already says
why. A deleted Application allows none.

| Action | The stage allows it when |
| --- | --- |
| `analyze` | no JobAnalysis exists for the active JobSnapshot |
| `edit_matching_configuration` | a JobAnalysis exists |
| `build_from_analysis` | a document exists and the newest analysis has a higher version than the document's |
| `create_draft` | a document exists and `content IS NULL` |
| `confirm_and_use_fact` | a review reason names it as a resolution action |
| `edit`, `regenerate_section`, `regenerate_claim` | `content IS NOT NULL` |
| `check` | `content IS NOT NULL` and `content_check != passed` |
| `approve` | `preparation_state = draft_in_progress` |
| `render` | `preparation_state = approved` |
| `submit`, `download_pdf` | `preparation_state = ready` |

A review reason's resolution actions are allowed too; `edit`, `regenerate_section` and
`regenerate_claim` only while content exists.

An allowed action is available unless a blocker withholds it. Then it is in
`blocked_actions` with every blocker's code:

| Code | Withholds |
| --- | --- |
| `ANALYSIS_IN_PROGRESS` | `analyze`, while an `analyze_job` is queued or running |
| `MATCHING_CONTEXT_OPERATION_IN_PROGRESS` | `edit_matching_configuration`, while an `analyze_job` is queued or running |
| `DOCUMENT_OPERATION_IN_PROGRESS` | `build_from_analysis`, `confirm_and_use_fact`, `create_draft`, `edit`, `regenerate_section`, `regenerate_claim`, `check`, `approve`, `render`, while a `create_draft`, `regenerate_section`, `regenerate_claim` or `render_document` is queued or running |
| any review reason code (§7) | `approve`, `render`, `submit` |
| `VALIDATION_FAILED` | `approve`, while `content_check = failed` |

`download_pdf` has no blocker: a Ready document stays downloadable.

`edit_matching_configuration` is committed through `apply_analysis_decisions` (§13); it
is an action name, not a separate endpoint.

`recommended_action`, first match wins, then nulled unless available: `analyze` when no
document exists; `create_draft` when content is NULL; `check` when `content_check` is
`none` or `outdated`; otherwise the first available of `approve`, `render`, `submit`.

## 10. RecruitmentStatus

```text
saved  applied  recruiter_screen  interview  assignment  final_stage  offer
accepted  rejected  withdrawn  closed
```

Allowed transitions:

```text
saved             -> applied | withdrawn | closed
applied           -> recruiter_screen | interview | rejected | withdrawn | closed
recruiter_screen  -> interview | assignment | rejected | withdrawn | closed
interview         -> assignment | final_stage | offer | rejected | withdrawn | closed
assignment        -> interview | final_stage | offer | rejected | withdrawn | closed
final_stage       -> offer | rejected | withdrawn | closed
offer             -> accepted | rejected | withdrawn | closed
accepted | rejected | withdrawn -> closed
closed            -> (none)
```

`saved -> applied` is owned by submission (§18): the status command refuses `applied`,
and `allowed_recruitment_transitions` never lists it.

`terminal_outcome` is set to `accepted`/`rejected`/`withdrawn` on entering that status,
kept on entering `closed`, and cleared on entering any other status. `closed` is
archival.

A backward move is not a transition. `correct_recruitment_status` appends a correction
event that references the erroneous one; current status and terminal outcome change in
the same transaction and the original event stays.

Preparation commands never change RecruitmentStatus. Drafting after `applied` leaves
the Application applied.

## 11. Operation lifecycle

Status: `queued`, `running`, `succeeded`, `failed`, `cancelled`, `interrupted`.

Phase: `queued`, `waiting_for_application`, `waiting_for_render_slot`, `executing`,
`completed`. A row stores `queued`, `executing`, or `completed`. The two waiting phases
are derived when a queued Operation is read: `waiting_for_application` while another
Operation of its Application runs, `waiting_for_render_slot` while another render runs
(architecture.md §10). A claim moves the Operation straight to `executing`; the checks
before execution and before activation are not phases of their own.

Types:

| Type | Bound to | Provider |
| --- | --- | --- |
| `analyze_job` | its JobSnapshot (ID and hash) and a Knowledge context hash | required |
| `create_draft` | `expected_document_hash` | required |
| `regenerate_section` | `expected_document_hash` | required |
| `regenerate_claim` | `expected_document_hash` | required |
| `render_document` | `expected_document_hash` | none (Playwright) |

Manual edits, `apply_analysis_decisions`, `build_from_analysis`,
`check`, `approve`, and `submit` are synchronous and never Operations. No provider call
happens inside an HTTP request.

A document-mutating Operation locks the document row at activation; a hash mismatch
discards the result and fails the Operation with `SOURCE_CHANGED`. Draft-producing
Operations do not re-check other input freshness at activation: their output is
unapproved, and `approve`/`render` validate against the current Knowledge.

AI Operations freeze the model and reasoning effort from the command, or from the
Settings defaults, into the immutable payload when queued. The worker never re-reads
Settings to decide what to run. Retry copies them from the original.

Failure codes:

```text
SOURCE_CHANGED               PROVIDER_TIMEOUT           PROVIDER_RATE_LIMITED
PROVIDER_QUOTA_EXHAUSTED     PROVIDER_UNAVAILABLE       PROVIDER_REFUSED
PROVIDER_NOT_CONFIGURED
INVALID_OUTPUT               CLAIM_REVIEW_UNCERTAIN     CLAIM_REVIEW_UNSUPPORTED
RENDER_FAILED                BROWSER_START_FAILED       MISSING_FACT_RENDERING
PRECONDITION_FAILED          INFRASTRUCTURE_FAILED      VALIDATION_EXECUTION_FAILED
CANCELLED_BEFORE_ACTIVATION
```

Every code is final: the runner never retries an Operation. A provider call is retried
at most once by the application before its failure is raised, per call and only where
the policy allows (architecture.md §11); a browser that fails to start is started once
more by the render handler.

- `PROVIDER_RATE_LIMITED`: the provider throttled the request; slowing down and trying
  later fixes it. `PROVIDER_QUOTA_EXHAUSTED`: the provider refused for billing - no
  credit left, or a spend or usage limit reached; waiting does not fix it, a change to
  the account does. Neither is retried automatically once raised; both keep the manual
  `retry`, for after the cause is fixed.

- `PROVIDER_NOT_CONFIGURED`: an AI task was requested with no provider configured;
  nothing was sent. `PROVIDER_REFUSED`: a provider answered and declined.
- `PRECONDITION_FAILED`: the workflow refused the run - the document, the Application,
  or Knowledge is not in a state the action accepts; changing that state fixes it.
  `INFRASTRUCTURE_FAILED`: storage the run needed failed - the database, the payload
  store, or the Knowledge files; a retry may succeed once it recovers.
  `VALIDATION_EXECUTION_FAILED`: the engine itself failed - an unexpected error, or no
  handler for the Operation type. All three activate nothing.
- `CLAIM_REVIEW_UNCERTAIN`: the semantic reviewer could not establish support for a
  proposed wording. `CLAIM_REVIEW_UNSUPPORTED`: it found the wording exceeds or
  contradicts the cited facts. Malformed output - an answer the output schema refuses,
  from any task - is `INVALID_OUTPUT`; the AI call log keeps the precise outcome
  (`schema_violation`). A writing
  Operation fails with these codes only when every line its answer named was withheld,
  and then the document is unchanged; otherwise it succeeds with `withheld_claims`.

An output is what a succeeded Operation activated, recorded in the transaction that
completed it; a failed or cancelled Operation has none. An output reference is one of
`job_analysis` or `cv_document`. Provider calls are not outputs; every attempt an Operation made is in the
AI call log, keyed by the Operation, whatever the Operation's outcome.

The Operation read returns status, phase, message, timestamps, failure code, safe
failure detail, structured `failure_reason`, `withheld_claims` (succeeded writing
Operations only), retry reference, cancellation state,
output references, provider/model/reasoning metadata, usage and cost summed over every
logged provider attempt (input, cached input, cache-write input, output, total, USD; an
attempt proven never delivered adds zero, and any other attempt without the value makes
that total NULL), and `available_actions`
(`cancel`, `retry`). The structured reason is the cause in a closed vocabulary with
typed parameters (a page count against its limit, a fact missing a rendering in a
language, a named render check); the detail is the same cause as an English sentence.
Clients explain a failure from the reason and never parse the sentence. The UI polls and
does not show fabricated progress.

For `CLAIM_REVIEW_UNCERTAIN` and `CLAIM_REVIEW_UNSUPPORTED`, a newly recorded failure
includes a `failure_reason` with `code=claim_review` and `claims`: claim ID, section,
preceding heading (nullable), proposed text, the policy's rejected verdict, each
cited canonical fact's ID, meaning and rendering as read for that review, and the
reviewer's explanation for that line (`rationale`, nullable). The same reason is
recorded on an `INVALID_OUTPUT` failure where the reviewer answered `supported` but its
evidence failed the deterministic review check: such a line has verdict `unattested` and
`problems`, the closed codes of the checks it failed (empty for every other verdict). In
a mixed failure every refused line is included; unsupported, then uncertain, determines
the Operation failure code. This is diagnostic context, not an accepted proposal or an
approval record. The explanation is the reviewer's opinion, shown as plain text to help
the user find what to fix; it is never evidence and authorizes nothing. Other provider
output, responses, credentials and internal paths are excluded. Existing failure records
remain unchanged and may have no context; one recorded before the explanation was kept
has none, and none is reconstructed.

A line the writer's answer named but the engine refused before review - a fact outside
the task's pool, no linked fact, wording the edit path rejects - has verdict `refused`
and no `problems`. Refused lines appear in the same reason, and a failure made only of
them is `INVALID_OUTPUT`.

A succeeded `create_draft`, `regenerate_section` or `regenerate_claim` records
`withheld_claims` when some of its answer's lines were withheld (product-spec §10.1): the
same `code=claim_review` shape, one entry per withheld line, recorded with the success
and never reconstructed. Each withheld line holds the wording it had before the
Operation; the entry carries the proposed wording that was not applied. The field is
NULL on every other Operation, and the database refuses it on any status but
`succeeded`. The UI opens the report for such a success, as it does for a failure, so
no line stays unchanged unseen.
Resolution uses the existing document editing and fact commands; no acknowledgement
command is introduced.

## 12. Application commands

### `duplicate_check`

Synchronous read. Takes the intake fields and returns duplicate matches with the reasons
they matched. Writes nothing.

### `create_application`

Input: company, target role, exact job text, optional source URL,
`acknowledged_duplicates`.

- Validates required fields, size, control characters, and an `http(s)` source URL. A
  refusal is `APPLICATION_INTAKE_INVALID` (412) naming the rejected field in `context`;
  the rejected value is never echoed.
- Reruns duplicate detection; unacknowledged matches are
  `DUPLICATE_ACKNOWLEDGEMENT_REQUIRED` (412) with the matches.
- Writes the JobSnapshot payload, then creates the
  Application in `saved` with its first snapshot in one transaction.
- Returns the IDs and duplicate warnings.

Synchronous, deterministic, never calls AI. Deleted Applications are excluded from
duplicate detection.

### `create_job_snapshot`

Input: Application ID, exact new text, optional URL and source metadata. Creates a new
immutable snapshot with the next version and makes it active. Text identical to an
existing snapshot of the Application is refused (409). Older snapshots, analyses, and
the document are not changed.

### `update_application_notes`

Synchronous. Replaces the Application's free-text notes, guarded by `expected_notes`
(the notes the client last read); a mismatch is 409 and writes nothing. Appends an
audit record.

### `close_application`

Transitions to `closed` through `transition_recruitment_status`, so it is refused where
that transition is not allowed. There is no hard delete.

### `delete_application`

Soft delete: sets `deleted_at` and appends an audit event, from any status, without
changing `current_status`. A deleted Application is excluded from the default list,
Dashboard counts, and duplicate detection. Its document and every immutable record it
produced stay unchanged and reachable by ID. There is no undelete. Deleting an already
deleted Application is 409.

Every command in §13–§18, and `close_application`, resolves its Application through
one shared precondition: 404 if it does not exist, 409 if it is deleted.
*Designed, not built (§23):* resolution is always for the signed-in user, and an
Application of another user is 404 exactly as if it did not exist; this applies to every
command and query below, including the ones exempt from the deleted check.
`create_job_snapshot` and `update_application_notes` check existence only. Reads of
history are exempt by design: the detail projection, document read, JobSnapshot
history, `export_recruiter_pdf`, `export_decision_markdown`, and previews.

## 13. Analysis commands

### `analyze_job(application_id, job_snapshot_id, model?, reasoning_effort?)`

Asynchronous Operation (`202`). Needs the configured provider; there is no rules-based
fallback. It runs the `propose_analysis` task (product-spec §12) and receives a
Proposal: requirements with importance, evidence-linked coverage, shortfall severity and
reason, and the Track/Profile/Emphasis/language classification. Every attempt is
appended to the AI call log.

Deterministic policy then locates each quoted requirement in the snapshot, checks
canonical-fact eligibility, refuses positive coverage without evidence, applies
canonical boundary facts, checks Profile legality, and derives requirement identity,
gaps, Fit, and review routing. A failed check narrows the requirement it names and is
recorded as an analysis issue; the rest of the reading stands. A check may narrow a
proposal, never widen it.

Activation writes one immutable JobAnalysis under the Application lock. When the
Application has no document, the same transaction creates it (§3) with `built_with` set
to the current versions. An existing document is not touched.

Preconditions: the snapshot belongs to the Application; the Application is not deleted.

Fit: `fit_score` is the weighted fraction of requirement coverage (mandatory weighted
double; `partial` earns half; `unknown` earns zero and is not excluded). `fit`
(`high`/`medium`/`low`) is read off fixed thresholds and then capped: two or more hard
gaps force `low`, exactly one caps at `medium`. `fit_score` is null only when nothing
could be scored. A mandatory `unsupported` requirement is a hard gap; a mandatory
`partial` one is hard only when its shortfall severity is `material`. Fit is diagnostic
and blocks nothing.

### `apply_analysis_decisions(analysis_id, ...)`

Synchronous (`201`). Input: `expected_analysis_id` (must equal the path's analysis),
`expected_document_hash` (required when a document exists), and any of
`track_override`, `profile_override`, `language_override`, `emphasis_override`.

Overrides accumulate: the submission is merged over the overrides the source analysis
already carries, and omitting a field does not retract it.

- **Classification change** (Track, Profile, language, or Emphasis differs from what the
  analysis already carries): creates one new immutable JobAnalysis without calling a
  provider, after checking Track/Profile/Emphasis consistency. The document is not
  changed: it reports `DOCUMENT_ON_OLDER_ANALYSIS` until `build_from_analysis`. With no
  document, the new analysis creates it. Under the Application lock it refuses while an
  `analyze_job` is queued or running, and refuses (409) when the newest analysis is no
  longer `expected_analysis_id`.
- **No change**: refused (412).

The response carries the resulting analysis ID, whether one was created, and the
document ID and hash. The client reads the fresh projection to choose the next step.

## 14. Document commands

### Wording evidence contract

Governs generation, regeneration, editing, checking, and approval. A claim is supported
by canonical, extractive, or presentation proof, or by complete eligible reviewed
evidence (product-spec §10.1). Positive reviewed evidence needs no per-claim user
confirmation. Uncertainty cannot be downgraded to a warning; a known contradiction or
unsupported content cannot be overridden by approval.

AI wording is proposed, then reviewed by the semantic reviewer against the exact
proposed claims, section context, linked fact IDs, allowed canonical sources, and an
ordered assertion-to-source mapping. The answer is judged line by line (product-spec
§10.1): a line becomes state only through a hard check it passes or a fully `supported`,
attested review, and any other line is withheld - it keeps exactly the wording, links and
proof it held before the Operation. The Operation succeeds with `withheld_claims` unless
every line its answer named was withheld; then it fails (§11) with the provider calls in
the AI call log and the document unchanged. Unsupported manual text is saved as a
pending, unlinked claim; it is never rejected or discarded, and it cannot pass the check.

### `read_document(application_id)`

Returns the document (§20) with `document_hash` as the ETag. 404 when the Application
has no document yet.

### `build_from_analysis(application_id, analysis_id, expected_document_hash)`

Synchronous and deterministic. Re-pins the document to a named JobAnalysis of the same
Application (412 if it is another Application's, or the one already pinned). The
command accepts any analysis of the Application; the projection offers it only when a
newer one exists. It sets `analysis_id`, fresh `built_with`, and `content = NULL`, and in the same write clears the report, all three
stamps, `html_path`, `pdf_path`, and `last_render_error`. The released rendered files
are deleted best-effort after commit.

### `create_draft(application_id, expected_document_hash, provider, model?, reasoning_effort?)`

Operation, only while `content IS NULL`. `provider` is always `openai`; there is no
rules-based form. The engine composes the frame from the analysis and the Profile:
per section, the pool of canonical facts, the structural facts that are always present,
and the section's guidance (product-spec §10). `draft_resume` chooses the facts per
section and proposes their wording. The engine refuses a chosen fact outside the
section's pool or not canonical, lays the chosen facts out in pool order, and activates
the wording through semantic review. Activation writes `content` only while
`document_hash == expected_document_hash`. A chosen or structural fact without a
rendering in the document language fails with `MISSING_FACT_RENDERING`.

### `update_document(application_id, If-Match, patch)`

Synchronous autosave. The patch has `claim_edits` (text, fact IDs, template),
`claim_removals`, `claim_additions` (section + text), and `claim_orders` (the complete
claim order per reordered section). Returns the new `document_hash`. A mismatch is 409.

- Free text that cannot be authorized is saved as a pending claim carrying the reason.
- Any section claim may be removed; the fact it linked leaves the dependent fact set.
  Headline and contacts are structural.

Editing an approved or Ready document is allowed; the basis changes and the document is
`draft` on the next read.

### `regenerate_section` / `regenerate_claim`

AI Operations against `expected_document_hash`, a named section or claim, and an
optional instruction. An unknown section or claim is 404. Both reword the facts the
section or claim already links; neither chooses facts again. `regenerate_claim` with
`keep_text` reviews the claim's own wording instead of rewriting it; it requires a
pending claim linked to at least one fact. Activation follows the `create_draft` hash
rule.

### Previews

`preview` (HTML) and `preview.pdf` render the current content through the render
composition, marked as an unapproved draft. They need no approval, store nothing, and
write no document field, Artifact, or Operation. 412 while `content IS NULL`.

## 15. Check and approval commands

### `check_document(application_id, expected_document_hash)`

Synchronous and deterministic; no provider. Runs the validation contract against the
current content, the document's analysis, and current Knowledge, and
stores `content_report`, `passed`, and `checked_basis` in one write — including when
`passed = false`. Content bound to another Application, analysis, or snapshot fails as
`document-binding-mismatch`. A validator execution failure stores nothing and is an
infrastructure error.

The report records issues, groups, evidence (including reviewed-wording proof
references), and validator versions. It checks hard rules, full assertion coverage,
permitted evidence kinds, absence of unresolved contradiction or uncertainty, and fact
eligibility. A missing review is never read as success.

### `approve_document(application_id, expected_document_hash)`

Synchronous. Validates and approves in one action:

1. Refuses a deleted Application, a hash mismatch, and `content IS NULL`.
2. If `approved_basis` and `checked_basis` already equal the basis, returns the
   existing approval: `approved_at` is not rewritten and no audit record is added.
3. Refuses with `KNOWLEDGE_RECONCILIATION_REQUIRED` (412) while any Knowledge mutation
   is quarantined.
4. Refuses with the first review reason's code (412).
5. Runs validation, then under the document row lock stores the report and
   `checked_basis`, and — only when the report passed — `approved_basis` and
   `approved_at`, with an audit record.

A failed check is returned as data (`200` with the report and `passed = false`), not as
an exception.

A no-pause flow (product-spec §11) orchestrates check -> approve -> render as explicit
user actions with `actor_type = user`, subject to every rule above.

## 16. Rendering commands

### `render_document(application_id, expected_document_hash)`

Operation. Admission (at queue time) requires the hash, `preparation_state = approved`
(else `DOCUMENT_NOT_APPROVED`, 412), and no review reason. Execution revalidates the
content against current Knowledge (failure: `ValidationBlocked`), writes HTML and
renders the PDF with Playwright Chromium to a unique per-attempt path, and checks
geometry, page count, PDF/ATS text, links, direction, and filename metadata. Rendering
runs outside database scopes.

Activation locks the document row and requires `document_hash == expected_document_hash`
and `approved_basis == basis`. Only then does it swap `html_path`/`pdf_path`, stamp
`rendered_basis`, and clear `last_render_error`. Render activation is the only writer of
`rendered_basis`.

A failure records `last_render_error` (the structured reason plus the hash it failed
against) only while `document_hash` still equals the expected hash; otherwise only the
Operation keeps it. A failure never touches the active files or `rendered_basis`.
Superseded and failed-attempt files are deleted best-effort. Rendered files are working
outputs, not Artifacts. After a failure the document stays approved; the fix is an edit
and a new render.

### `export_recruiter_pdf(application_id)`

Synchronous read. Computes the basis at request time and refuses with
`DOCUMENT_NOT_READY` (412) unless `preparation_state = ready`. Verifies path containment
and existence, then streams the file with a friendly Content-Disposition filename and
the document hash as ETag.

### `export_decision_markdown(application_id)`

A human-readable provenance export of the current document: its analysis,
dependent facts, and stored content report. Writes nothing.

## 17. Knowledge commands

Every fact mutation runs through the Knowledge mutation journal
(architecture.md §7.2). While any mutation is quarantined, every fact mutation is
refused (`KNOWLEDGE_REJECTED`, 412) and approval is refused (§15).
*Designed, not built (§23):* facts are the signed-in user's, in PostgreSQL; a fact
mutation is one transaction, and the journal and quarantine are retired along with
these two refusals. A `fact_id` is unique per user, and another user's fact is 404.
Attachment targets are the user's Profile binding over the shared templates.

Fact statuses: `pending`, `canonical`, `deleted`. The lifecycle is
`pending -> canonical` on one explicit confirmation; any live fact may be deleted.

### Reads

- `list_facts(status?)`: without a filter excludes `deleted`; `status=deleted` lists
  them. Each item carries the fact and its last recorded lifecycle status.
- `show_fact(fact_id)`: one fact with its events, including a deleted fact.
- `fact_history(fact_id?)`: lifecycle events, for one fact or all.
- `list_fact_attachment_targets(fact_id?)`: existing Profiles and their sections as
  read-only targets (stable identifiers and labels; with `fact_id`, whether it is already
  attached or pinned there). A deleted `fact_id` is 404. No stored paths, policies, or
  Profile editing.

None of these need an Application or document context.

### `create_pending_fact`

Creates a pending fact with a generated ID (a client-supplied ID is refused). Input:
source file, meaning, renderings (`en` required, `he` optional), tags, provenance,
`resume_style`, optional effective dates, optional `replaces`, reason. With `replaces`
naming a canonical fact it is a pending correction; the original is not changed.

### `confirm_fact(fact_id)`

Moves exactly `pending -> canonical`. It needs an explicit `confirm: true` attestation
in the request; `false` is refused, not ignored. Any other source status is refused.
It sets `confirmed_at` when the fact has none and advances the source file's version.
Confirming a replacement makes the original superseded for warning purposes (§8); it
rewrites neither the original nor any Submission.

### `delete_fact(fact_id)`

Explicitly confirmed, one-way move from `pending` or `canonical` to
`deleted`; an already deleted fact is refused. The record and its history stay
reachable. Deletion is always allowed, even for a fact attached to a Profile or used by
a document, and writes nothing to any document: a dependent document's basis changes
and it reports `FACT_DELETED_REQUIRES_RESOLUTION` (§7). Submissions are unaffected.
Deletion does not create a replacement, and a replacement does not delete the original.

A deleted fact is refused by `confirm_fact`, `attach_fact`, and
`confirm_and_use_fact`.

### `attach_fact(fact_id, profile, section, pin=false)`

Offers one canonical fact to one existing Profile section's pool, optionally pinned.
Non-canonical facts are refused. It changes no Profile structure and no document.

### `confirm_and_use_fact(fact_id, application_id, job_analysis_id, profile, section)`

One journaled command:

```text
pending -> canonical
-> attach to the named Profile section
```

Preconditions, checked before any write: the document exists and is built on
`job_analysis_id`; the analysis belongs to the Application and its Profile is `profile`.
It writes no document: a claim already linking the fact stops raising
`PENDING_FACT_REQUIRES_RESOLUTION`, and the next `create_draft` can choose the fact.
Every transition gets its own event. Partial completion is never visible.

### `create_fact_from_claim(application_id, claim_id, ...)`

Turns a claim of the current document into a pending fact, copying the claim's exact
text as a rendering without rewrite. Meaning, tags, and provenance are supplied
explicitly; a Hebrew document also needs the English rendering. The headline cannot
become a fact. The claim is not authorized until the fact completes its lifecycle and
is in its section's pool.

Canonical correction always creates a replacement fact carrying `replaces`; it never
mutates the old fact. `delete_fact` is the only removal. Archive, withdrawal,
retirement, and known-incorrect transitions do not exist; a client must not present
them.

## 18. Tracking commands

### `submit_application(application_id, expected_document_hash, submitted_at, metadata)`

Records a send that already happened. Requires the hash, `preparation_state = ready` with
both files present (`DOCUMENT_NOT_READY`, 412), and no review reason. Copies the
rendered HTML and PDF to submission-owned paths, computing
a SHA-256 per file. Then, in one transaction under the document row lock, re-checks that
the hash, stamps, and file paths are unchanged, inserts the immutable Submission,
transitions `saved -> applied` when the Application is `saved`, and appends status and
audit events.

An internal Submission records its content, `document_hash`, the `job_snapshot_id` of
the document's analysis (FK `RESTRICT`), `html_path`/`html_sha256`,
`pdf_path`/`pdf_sha256`, `submitted_at`, and metadata.

When the document is on an older analysis or snapshot, the result carries the
`DOCUMENT_ON_OLDER_ANALYSIS` warning; it is not a precondition. Multiple submissions
are allowed; later ones add no transition. Submitting does not change the document.

### `record_external_submission(application_id, submitted_at, metadata)`

Records an immutable external submission with no content or files and the same
`saved -> applied` rule.

### `transition_recruitment_status(application_id, target_status, reason?, occurred_at?)`

Applies one allowed transition (§10). `applied` is refused (submission-owned); an
unknown or disallowed target is 409. Targeting the current status is a no-op that
returns the current state and writes nothing.

### `correct_recruitment_status(application_id, target_status, corrects_event_id, reason)`

Requires a non-blank reason and a status event of this Application (not a next-action
event); an unknown event is 404, a foreign or wrong-kind event 409. Appends a
correction event and updates status and terminal outcome in one transaction. The
corrected event is not changed.

### `set_next_action(application_id, next_action?, next_action_date?)`

Sets or clears the one active next action and date, appending an event. Overdue is
computed on read (§8); no notification job exists.

## 19. Operation commands

### `get_operation(operation_id)`

The Operation read (§11).

### `cancel_operation(operation_id)`

A queued Operation becomes `cancelled` immediately. A
running one records `cancellation_requested_at`; it then ends `cancelled` without
activating anything, and records no output.

### `retry_operation(operation_id, Idempotency-Key?)`

Creates a new Operation with `retry_of_operation_id`, the original payload, and the
original model and reasoning effort. Only a terminal Operation can be retried (409
otherwise). A document-mutating retry carries the document's current `document_hash`
as its `expected_document_hash`; if the document no longer exists it is 409. The
original stays unchanged.

`MISSING_FACT_RENDERING` and `SOURCE_CHANGED` failures expose no `retry` action: the
first needs a changed fact, the second a new command against the current
document.

### Idempotency

Every asynchronous command accepts an optional `Idempotency-Key`; the boundary
generates one when absent. Keys are scoped per Operation type. Reusing a key with the
same payload returns the existing Operation; with a different payload it is
`IDEMPOTENCY_KEY_REUSED` (409). *Designed, not built (§23):* keys are also scoped per
Application (architecture.md §18.3), so a key another user already used is a new key,
never their Operation.

## 19a. Settings commands

*Designed, not built (§23):* settings are per user; each user has one row with its own
`edit_version`. Provider configuration stays the operator's and is only reported.

### `read_settings()`

Returns the safe settings, `edit_version` (as ETag), whether a provider is configured,
and the allowlisted model catalog.

### `update_settings(If-Match, settings)`

Writable fields: `ui_theme`, `ui_density`, `ui_text_size`, `default_ai_model` and
`default_reasoning_effort` (closed backend allowlists), and
`auto_generate_when_review_not_required`. The write is optimistic on `edit_version`; a mismatch is 409 and
changes nothing, and each successful write increments it. On conflict the client keeps
its local edits, reads the current version, and lets the user choose what to reapply;
there is no automatic overwrite. Arbitrary model IDs, per-task overrides, timezone, and
secrets are never writable.

## 19b. Maintenance commands

*Designed, not built (§23):* both commands span every user, so they leave the API and
become operator CLI commands with the same semantics. No user route reaches them.

### `reconcile()`

`POST /api/v1/maintenance/reconciliations`. Checks database references and stored
hashes against the payload store — JobSnapshot payloads and every Submission file
against its SHA-256 (`payloads_checked`) — every logged AI call's sanitized response
against its `sanitized_response_hash` (`ai_calls_checked`), and the fact lifecycle
against its trail: events for facts that no longer exist, live statuses the trail never
recorded or contradicts, and prepared or quarantined journal mutations. Every part
always runs.

It reports and never repairs: the records it checks are immutable, and a repair would
destroy the evidence. `passed` is the conjunction of every part. A failed
reconciliation is a successful answer (`200`). The document's rendered files are
mutable and not checked.

### `inspect_orphans()`

`GET /api/v1/maintenance/orphans` returns `candidates`: a sorted list of managed
immutable payload references found in storage that no database row references and that
were stored longer than one hour ago (`ORPHAN_MIN_AGE`, architecture.md §7.1). A younger
unregistered payload may still be on its way to registration and is not listed.
References cover JobSnapshots and Submission files. Rendered document files and files
outside managed layouts are excluded.

Storage enumeration happens outside the database read. The result is a read-only,
non-atomic observation; it changes no reconciliation verdict and deletes nothing.

There is no reclaim command. Nothing deletes an immutable payload, so an orphan stays in
storage and is only reported (architecture.md §7.1).

## 20. Queries

- **Application list** (`GET /applications`): filters `activity` (`open` | `closed` |
  `all`), `stage` (PreparationStates), `recruitment_status`, `preset`
  (`needs_attention` = any review reason or warning; `ready_to_send` =
  `preparation_state = ready`; `active_interviews` = `recruiter_screen` through `offer`), `search`; `sort`
  (`updated` | `created` | `company` | `stage`); `limit` (1–200) and `offset`. Each row
  carries the §9 projection and `is_closed`. The response carries `matched` and
  preparation-state, preset, and recruitment-status counts from the same projected
  read; each facet ignores its own selected value and respects the other filters.
  Deleted Applications are excluded.
- **Application detail**: the §9 projection plus the Application, latest snapshot and
  analysis, `allowed_recruitment_transitions`, and the unified recruitment timeline.
  Reachable for a deleted Application.
- **Duplicate check** (§12).
- **JobSnapshot history**: the active snapshot ID and every snapshot in version order
  with ID, version, capture time, source URL, and exact verified text. Unreadable or
  unverified text is NULL. It never fetches the live posting, repairs a payload, or
  changes the active snapshot.
- **CVDocument**: ID, analysis ID, content and its
  outline, language, dependent facts, `built_with`, `document_hash` (ETag), content
  report and `content_check`, `preparation_state`, `approved_at` (as in §9),
  `last_render_error`, timestamps.
- **Document previews** (§14).
- **Operation** (§11).
- **Facts**: list, detail, history, attachment targets (§17).
- **Settings** (§19a) and **health**: runtime and provider configuration status without
  secrets.

There is no revision history and no revision comparison. The history of what was sent
is the list of Submissions.

*Designed, not built (§23):* every query above returns only the signed-in user's
records, and every list, count, and facet is computed over them alone. Health returns
only liveness and versions to an anonymous caller.

Queries return DTOs, never database rows or local paths.

## 21. HTTP mapping

Every command and query maps to `/api/v1` without a second business contract. The
generated OpenAPI document (`openapi/openapi.json`) is the authoritative endpoint
inventory; the sections above stay authoritative for sources, preconditions,
idempotency, and synchronous versus asynchronous behavior.

- Synchronous creation returns `201`; an accepted Operation returns `202` with a
  `Location` naming the Operation to poll.
- The document is read and written at `/applications/{id}/document`. Its
  `document_hash` travels as a strong ETag. Only `PATCH` (autosave) takes it as
  `If-Match`; a weak or malformed value is 412. Every document action carries it in the
  body as `expected_document_hash`, because an action on a resource is not a conditional
  replacement of it.
- Settings use the ETag `"settings-<edit_version>"` with `If-Match` on `PATCH`.
- CORS exposes `ETag`, `Location`, and `Content-Disposition`, and allows `If-Match` and
  `Idempotency-Key`.
- *Designed, not built (§23):* the session travels only in its cookie. Every route
  requires a session except `login` (§23) and health.

## 22. HTTP outcomes

The status comes from the refusal's class, never its message:

| Status | Meaning |
| --- | --- |
| `200` | query, synchronous update, or a successful outcome such as a failed check or reconciliation |
| `201` | synchronous creation |
| `202` | accepted Operation with `Location` |
| `401` | *designed, not built:* no valid session (`AUTHENTICATION_REQUIRED`), failed sign-in (`INVALID_CREDENTIALS`), or a wrong current password (`REAUTHENTICATION_FAILED`) |
| `403` | refused Origin or Host (`ORIGIN_NOT_ALLOWED`). Never used for another user's record |
| `404` | unknown record (`UNKNOWN_RECORD`), including a document not yet created, an unknown route, and — *designed, not built* — a record of another user |
| `409` | state conflict: hash, notes, or settings mismatch; deleted Application; disallowed status transition; duplicate snapshot; idempotency-key payload mismatch |
| `412` | a named state cannot satisfy the command: missing precondition, blocker, review reason, intake refusal, lineage or Knowledge refusal |
| `413` | body limit exceeded |
| `422` | request does not match the schema (`REQUEST_VALIDATION_FAILED`) |
| `429` | *designed, not built:* rate limit (`RATE_LIMITED`) or AI quota (`AI_QUOTA_EXCEEDED`), with `Retry-After` |
| `500` | infrastructure failure |
| `503` | a required collaborator is not configured |

Problem Details (`application/problem+json`) carries `type`, `title`, `status`, a stable
`code`, a safe `detail`, and an optional safe `context`. It never contains a stack
trace, local path, provider response, or secret.

A refusal's `code` defaults to its class name in upper snake case (`STATE_CONFLICT`,
`PRECONDITION_FAILED`, `KNOWLEDGE_REJECTED`, `LINEAGE_BROKEN`, `VALIDATION_BLOCKED`,
`APPLICATION_INTAKE_INVALID`, ...). These codes are contracted by name:

```text
DOCUMENT_CHANGED                    DOCUMENT_NOT_APPROVED
DOCUMENT_NOT_READY                  MISSING_FACT_RENDERING
DUPLICATE_ACKNOWLEDGEMENT_REQUIRED  IDEMPOTENCY_KEY_REUSED
KNOWLEDGE_RECONCILIATION_REQUIRED   PENDING_FACT_REQUIRES_RESOLUTION
FACT_DELETED_REQUIRES_RESOLUTION
```

Review reasons, warnings, and validation issues are data in the projection, not
exceptions. They become a refusal only when a command they block is attempted.

## 23. Account commands

*Designed, not built.* Product rules: product-spec.md §22. Mechanisms, tables, and
default limits: architecture.md §18. Why: `../decisions/multi-user-accounts.md`.

Routes are under `/api/v1/auth`. Bodies are JSON; every mutation passes the Origin
check (architecture.md §14). A session is an opaque cookie; no route returns a token in
a body. `login` is the only route that needs no session.

### `login(email, password)`

`POST /auth/login`. Rate limited first: past the limit it is `429 RATE_LIMITED` with
`Retry-After`, whatever the credentials. On success creates a new session, sets its
cookie, records `login`, and returns `me`. On any failure — unknown email, wrong
password, deactivated account — answers `401 INVALID_CREDENTIALS` with the same body and
comparable timing, and records `failed_login`.

### `logout()` / `logout_all()`

`POST /auth/logout` revokes the current session and clears the cookie.
`POST /auth/logout-all` revokes every session of the user, the current one included.
Both `204` and record `logout`.

### `me()`

`GET /auth/me`: the user's ID, email, and `created_at`; `401` with no valid session. The
Web client calls it at startup to choose between the signed-in and signed-out shells.

### `change_password(current_password, new_password)`

`POST /auth/change-password`. A wrong current password is `401 REAUTHENTICATION_FAILED`
and changes nothing; a new password outside the policy is `422 PASSWORD_POLICY_FAILED`,
naming only the rule. On success revokes every other session, rotates the current one,
and records `password_changed`.

### `deactivate_account(current_password)`

`POST /auth/account/deactivate`. There is no account deletion; this is the whole
contract. It re-authenticates (`401 REAUTHENTICATION_FAILED` changes nothing), then in
one transaction:

1. **Deactivate:** `is_active = false`, `deactivated_at` set; sign-in is refused from
   now on with the ordinary `INVALID_CREDENTIALS`.
2. **Revoke sessions:** every session of the user, the current one included.
3. **Anonymize permitted PII** — only mutable fields, each named here:
   `users.email` becomes a non-deliverable pseudonym derived from the user ID;
   `users.password_hash` becomes NULL; every Application's `notes`, `next_action`, and
   `next_action_date` become NULL; every CVDocument's `content` becomes empty; every
   fact's content columns are erased (status kept); the `candidate_contexts` and
   `profile_bindings` rows and the user's `user_settings` row are deleted.
4. **Record** `account_deactivated` in `auth_events`.

Nothing immutable is touched: Submissions, JobSnapshots, the AI call log,
`fact_events`, recruitment and audit events, and terminal Operations stay as written,
owned by the now-anonymous user (product-spec.md §22). `204`; the cookie is cleared.
There is no reactivation.

### Operator commands

`create-user`, `set-password`, and `import-knowledge` are operator CLI commands
(architecture.md §18.7), not routes. `set-password` revokes every session of the user.

### Codes

```text
AUTHENTICATION_REQUIRED     INVALID_CREDENTIALS       REAUTHENTICATION_FAILED
PASSWORD_POLICY_FAILED      RATE_LIMITED              AI_QUOTA_EXCEEDED
```

`AI_QUOTA_EXCEEDED` (429) is returned by any command that would queue an AI Operation
(§11), including `retry_operation`, when the user's quota is spent; nothing is queued.
