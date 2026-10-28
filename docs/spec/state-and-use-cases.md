# State and Use-Case Contracts

States, commands, queries, preconditions, outcomes, and the action policy the API
returns. Product behavior: [`product-spec.md`](product-spec.md). Section numbers are
cited from code; keep them stable.

## 1. Purpose

Commands name the sources they act on: an immutable source by ID, the CVDocument by its
Application plus the `expected_document_hash` the client last read. Only queries resolve
"latest".

Every write records `actor_type` (`user` | `system`) and `client` (`web` | `worker`).
Every command and query runs for one signed-in user and reaches only that user's
records; the worker acts for the owner of the Operation.

## 2. Entity lifecycle summary

Mutable:

- the Application: recruitment status, terminal outcome, notes, next action,
  `deleted_at`, and the job text until its first Submission (§12)
- one CVDocument per Application
- the user's Settings row
- the user, their sessions, and their facts' current status

Immutable or append-only:

- the job text once the Application has a Submission
- JobAnalysis
- Submission, with its content and copied files
- the AI call log (one row per provider call attempt)
- recruitment, status, audit, and fact lifecycle events
- a terminal Operation

There is no approval history and no draft history.

## 3. The CVDocument and its basis

```text
job text (on the Application)  ->  JobAnalysis (immutable, names the job_text_hash it read)
                                   |
                                   v
CVDocument (mutable, one per Application)
  analysis_id                       the analysis it is pinned to
  content                           the DraftDocument; NULL until generated
  template                          the chosen render template; NULL = the track's own
  built_with                        profile_version
  document_hash                     stored: hash(analysis_id, content, template)
  content_report, passed, checked_basis
  approved_basis, approved_at
  rendered_basis, html_path, pdf_path, last_render_error
```

`document_hash` is the SHA-256 of the canonical JSON of `analysis_id`, `content`, and
`template` when one is set (a NULL template adds no key, so a document that never chose
one keeps the hash it had before templates existed), rewritten by every command that
changes any of them. A command that changes the document
carries `expected_document_hash`; a mismatch is `DOCUMENT_CHANGED` (409) and writes
nothing.

The **dependent fact set** is every fact ID cited by the headline, contact, and section
claims in `content` (empty while `content IS NULL`).

`facts_hash` is the SHA-256 of the canonical JSON of each dependent fact's current record
(status included), sorted by ID; a missing fact is entered as missing. Computed on read.

```text
basis = sha256(document_hash + ":" + facts_hash)
```

The basis is computed on read. Three stamps are stored:

- `checked_basis`: the basis `content_report` was produced for;
- `approved_basis`: the basis that was approved;
- `rendered_basis`: the basis whose files `html_path`/`pdf_path` hold.

A NULL stamp never equals the basis. Any change to the document or a dependent fact
changes the basis; no command clears stamps.

Pinning:

- The first activated analysis creates the document pinned to it with no content.
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

A review reason (§7) blocks actions but does not change the PreparationState. A newer
analysis or edited job text does not change it either; it is the
`DOCUMENT_ON_OLDER_ANALYSIS` warning.

## 5. Content check

```text
none        no document, content IS NULL, or checked_basis IS NULL
outdated    checked_basis != basis
failed      checked_basis == basis AND passed = false
passed      checked_basis == basis AND passed = true
```

An outdated report is still returned for display; it authorizes nothing.

## 6. Why nothing goes stale

- A content edit, re-pin, or template change changes `document_hash`, outdating every
  stamp.
- A change to a dependent fact changes `facts_hash`, outdating every stamp. An
  unrelated fact does not.
- A newer analysis or edited job text is the `DOCUMENT_ON_OLDER_ANALYSIS` warning.
- A Profile version change is the `PROFILE_CHANGED` warning; approval and rendering
  validate against current Knowledge regardless.

## 7. Review reasons

Computed over the dependent fact set (§3):

```text
PENDING_FACT_REQUIRES_RESOLUTION     a dependent fact is pending
FACT_DELETED_REQUIRES_RESOLUTION     a dependent fact has status deleted
```

Each carries a message, `document_id`, the first offending `fact_id`, and resolution
actions:

| Reason | Resolution actions |
| --- | --- |
| `PENDING_FACT_REQUIRES_RESOLUTION` | `confirm_and_use_fact`, `edit` |
| `FACT_DELETED_REQUIRES_RESOLUTION` | `edit`, `regenerate_section`, `regenerate_claim` |

A review reason blocks `approve`, `render`, and `submit` (412, `code` = the first
reason). It does not block editing or regeneration.

Analysis issues, Fit, and gaps are not review reasons and block nothing.

## 8. Warnings, blockers, and failures

- A warning is shown and disables nothing.
- A blocker disables actions (`blocked_actions`, §9).
- A review reason is a blocker (§7).
- An error is a refusal or Operation failure, not domain state.

Warning codes:

- `DOCUMENT_ON_OLDER_ANALYSIS`: the document's analysis is not the newest, or it read a
  job text other than the current one.
- `PROFILE_CHANGED`: `built_with` differs from the current Profile version.
- `FACT_SUPERSEDED`: a canonical fact `replaces` a dependent fact. (Goes away once
  `edit_fact` ships, §17.)
- `NEXT_ACTION_OVERDUE`: `next_action_date` is past and the status is not `accepted`,
  `rejected`, `withdrawn`, or `closed`.
- `REQUIREMENT_NOT_IN_DOCUMENT`: the document has content and is on the current
  analysis, and a requirement of that analysis that is `mandatory`, `matched` or
  `partial`, and lists supporting facts has none of them among the facts the content
  links (`requirements_missing_from_document`). One warning for all such requirements:
  `entity_references` carries `document_id`, `job_analysis_id`, the first
  `requirement_id` with one of its supporting `fact_id`s, and `requirement_count`; the
  message lists every requirement's text.

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
  "job_text_hash": "...",
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

All inputs are captured in one read. Action identifiers are command names. Detail also
returns `allowed_recruitment_transitions` (§10), `job_posting` (text, source URL,
`job_text_hash`, `job_text_updated_at`, `locked`), the latest analysis, and the
timeline.

- `approved_at` is reported only while `approved` or `ready`.
- `last_render_error` is reported only while its recorded hash equals `document_hash`.
- `active_operation` is the queued/running Operation; `latest_operation` is the newest
  one, live or terminal.

An action the stage does not allow appears in neither list. A deleted Application
allows none.

| Action | The stage allows it when |
| --- | --- |
| `analyze` | no JobAnalysis exists for the current `job_text_hash` |
| `edit_matching_configuration` | a JobAnalysis exists |
| `build_from_analysis` | a document exists and a newer analysis than its own exists |
| `create_draft` | a document exists and `content IS NULL` |
| `confirm_and_use_fact` | a review reason names it |
| `edit`, `regenerate_section`, `regenerate_claim` | `content IS NOT NULL` |

`set_document_template` (§14) is not a projected action: like an edit it is guarded by
`expected_document_hash`, so an Operation queued against the old hash discards its
result.
| `check` | `content IS NOT NULL` and `content_check != passed` |
| `approve` | `preparation_state = draft_in_progress` |
| `render` | `preparation_state = approved` |
| `submit`, `download_pdf` | `preparation_state = ready` |

A review reason's resolution actions are allowed too (editing ones only while content
exists).

An allowed action is available unless a blocker withholds it:

| Code | Withholds |
| --- | --- |
| `ANALYSIS_IN_PROGRESS` | `analyze`, while an `analyze_job` is queued or running |
| `MATCHING_CONTEXT_OPERATION_IN_PROGRESS` | `edit_matching_configuration`, while an `analyze_job` is queued or running |
| `DOCUMENT_OPERATION_IN_PROGRESS` | `build_from_analysis`, `confirm_and_use_fact`, `create_draft`, `edit`, `regenerate_section`, `regenerate_claim`, `check`, `approve`, `render`, while a `create_draft`, `regenerate_section`, `regenerate_claim`, or `render_document` is queued or running |
| any review reason code (§7) | `approve`, `render`, `submit` |
| `VALIDATION_FAILED` | `approve`, while `content_check = failed` |
| `JOB_TEXT_CHANGED` | `create_draft`, while the document's analysis read a job text other than the current one |

`download_pdf` has no blocker.

`edit_matching_configuration` is committed through `apply_analysis_decisions` (§13).

`recommended_action`, first match, then nulled unless available: `analyze` when no
document exists; when content is NULL, `create_draft` if the current job text has an
analysis, else `analyze`; `check` when `content_check` is `none` or `outdated`;
otherwise the first available of `approve`, `render`, `submit`.

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

`saved -> applied` happens only through submission (§18); the status command refuses
`applied`.

`terminal_outcome` is set on entering `accepted`/`rejected`/`withdrawn`, kept on
entering `closed`, and cleared otherwise.

A backward move is a correction (`correct_recruitment_status`), not a transition.

Preparation commands never change RecruitmentStatus.

## 11. Operation lifecycle

Status: `queued`, `running`, `succeeded`, `failed`, `cancelled`, `interrupted`.

Phase: `queued`, `waiting_for_application`, `waiting_for_render_slot`, `executing`,
`completed`. Rows store `queued`, `executing`, or `completed`; the waiting phases are
derived on read (architecture.md §10).

| Type | Bound to | Provider |
| --- | --- | --- |
| `analyze_job` | `job_text_hash` and a Knowledge context hash | required |
| `create_draft` | `expected_document_hash` | required |
| `regenerate_section` | `expected_document_hash` | required |
| `regenerate_claim` | `expected_document_hash` | required |
| `render_document` | `expected_document_hash` | none (Playwright) |

Everything else is synchronous. No provider call happens inside an HTTP request.

A document-mutating Operation locks the document row at activation; a hash mismatch
fails it with `SOURCE_CHANGED` and discards the result.

Model and reasoning effort are fixed into the payload when queued; retry copies them.

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

The runner never retries an Operation. A provider call is retried at most once where
safe (architecture.md §11); a browser that fails to start is started once more.

- `PROVIDER_RATE_LIMITED`: throttled; retry later. `PROVIDER_QUOTA_EXHAUSTED`: billing
  limit; fix the account, then retry.
- `PROVIDER_NOT_CONFIGURED`: no provider; nothing sent. `PROVIDER_REFUSED`: the provider
  declined.
- `PRECONDITION_FAILED`: the document, Application, or Knowledge is not in an accepted
  state. `INFRASTRUCTURE_FAILED`: database, payload store, or policy files failed.
  `VALIDATION_EXECUTION_FAILED`: unexpected engine error.
- `CLAIM_REVIEW_UNCERTAIN` / `CLAIM_REVIEW_UNSUPPORTED`: the reviewer could not
  establish support, or found the wording exceeds the facts. `INVALID_OUTPUT`: output
  the schema refuses. A writing Operation fails with these only when every line was
  withheld; otherwise it succeeds with `withheld_claims`.

An Operation's output is what it activated (`job_analysis` or `cv_document`); failed
and cancelled Operations have none. Every provider attempt is in the AI call log, keyed
by Operation.

The Operation read returns status, phase, message, timestamps, failure code, failure
detail, structured `failure_reason`, `withheld_claims`, `page_fit`, retry reference, cancellation
state, outputs, provider/model/effort, summed usage and cost (NULL if any attempt's
value is unknown, except attempts never delivered), and `available_actions` (`cancel`,
`retry`). Clients explain failures from `failure_reason`, not the text.

**Claim review reason.** For `CLAIM_REVIEW_*` failures, for `INVALID_OUTPUT` where a
`supported` answer failed the deterministic evidence check, and for `withheld_claims` on
a success, `failure_reason` has `code=claim_review` and `claims`, one per refused line:
claim ID, section, preceding heading, proposed text, verdict, each cited fact's ID,
meaning, and rendering as read, the reviewer's `rationale` (nullable), and `problems`
(failed check codes, for verdict `unattested`). A line refused before review (fact
outside the pool, no linked fact, edit-path refusal) has verdict `refused`. This is
recorded at the time and never reconstructed. `withheld_claims` is NULL except on
succeeded writing Operations.

**Page fit.** A succeeded `create_draft` records `page_fit` (`code=page_fit`): `status`
(`fits`, `trimmed`, `over`, or `unavailable`), the last page count measured (`pages`,
NULL if none), the Profile's `maximum`, and `trimmed`, one entry per line dropped to fit
- claim ID, section, preceding heading, and text as it read before it was dropped
(product-spec §10). A dropped line is removed from `withheld_claims`. Recorded at the
time, never reconstructed. `page_fit` is NULL on every other Operation, on any
Operation that did not succeed, and on one cancelled before activation.

## 12. Application commands

### `duplicate_check`

Synchronous read: returns duplicate matches and why they matched.

### `create_application`

Input: company, target role, job text, optional source URL, `acknowledged_duplicates`.

- Validates required fields, size, control characters, and `http(s)` URL; refusal is
  `APPLICATION_INTAKE_INVALID` (412) naming the field.
- Reruns duplicate detection; unacknowledged matches are
  `DUPLICATE_ACKNOWLEDGEMENT_REQUIRED` (412).
- Creates the Application in `saved` with its job text, `job_text_hash`, and normalized
  hash.
- Returns the Application ID, `job_text_hash`, and duplicate warnings.

Calls no AI. Deleted Applications are excluded from duplicate detection.

### `update_job_text`

Input: new text, optional URL, `expected_job_text_hash`. Replaces the job text in place
and appends an audit record with both hashes. A hash mismatch is 409. Unchanged input
writes nothing. After any Submission it is refused (409), also enforced by the trigger
`lock_submitted_job_text`.

### `update_application_notes`

Replaces notes, guarded by `expected_notes` (409 on mismatch). Appends an audit record.

### `close_application`

Transitions to `closed` through `transition_recruitment_status`.

### `delete_application`

Soft delete: sets `deleted_at` and appends an audit event, from any status. The
Application leaves the default list, counts, and duplicate detection; its records stay
reachable by ID. No undelete. Deleting twice is 409.

Every command in §13–§18 and `close_application` resolves its Application the same way:
404 if missing or another user's, 409 if deleted. `update_job_text` and
`update_application_notes` check existence only. Reads (detail, document, exports,
previews) work on deleted Applications.

## 13. Analysis commands

### `analyze_job(application_id, job_text_hash, model?, reasoning_effort?)`

Operation (`202`), requires a provider. Runs `propose_analysis` (product-spec §12), then
applies the engine checks (product-spec §2). A failed check narrows the requirement and
records an analysis issue.

Activation writes one JobAnalysis with the `job_text_hash` it read. If the Application
has no document, the same transaction creates it (§3).

Preconditions: `job_text_hash` is current (409 at queueing; `SOURCE_CHANGED` at
activation); the Application is not deleted.

Fit: `fit_score` is the weighted fraction of coverage (mandatory weighs 2, others 1;
`matched` 1, `partial` 0.5, `unsupported` and `unknown` 0). `fit` is `high` at ≥ 0.85,
`medium` at ≥ 0.55, else `low`; one hard gap caps it at `medium`, two or more force
`low`. A hard gap is a mandatory requirement that is `unsupported`, or `partial` with
`material` shortfall. `fit_score` is null when there are no requirements. Fit blocks
nothing. Code: `cv_engine/domain/analysis/projection.py`.

### `apply_analysis_decisions(analysis_id, ...)`

Synchronous (`201`). Input: `expected_analysis_id`, `expected_document_hash` (when a
document exists), and any of `track_override`, `profile_override`, `language_override`,
`emphasis_override`. Overrides accumulate over the source analysis's.

- **Change:** creates a new JobAnalysis without a provider call, after checking
  Track/Profile/Emphasis consistency. The document reports `DOCUMENT_ON_OLDER_ANALYSIS`
  until `build_from_analysis` (or is created if none exists). Refused while an
  `analyze_job` runs, and 409 if the newest analysis is no longer
  `expected_analysis_id`.
- **No change:** 412.

Returns the analysis ID, whether one was created, and the document ID and hash.

## 14. Document commands

### Wording evidence

A claim is supported by canonical, extractive, or presentation proof, or by complete
reviewed evidence (product-spec §10.1). AI wording is reviewed line by line; failing
lines are withheld (§11). Unsupported manual text is saved as a pending claim and
cannot pass the check.

### `read_document(application_id)`

Returns the document (§20) with `document_hash` as ETag. 404 before the document
exists.

### `build_from_analysis(application_id, analysis_id, expected_document_hash)`

Synchronous. Re-pins the document to another analysis of the same Application (412 if
it belongs elsewhere or is already pinned). Sets `analysis_id`, fresh `built_with`,
`content = NULL`, and clears the report, all stamps, file paths, and
`last_render_error`. Old rendered files are deleted after commit.

### `set_document_template(application_id, template, expected_document_hash)`

Synchronous. Chooses the template the document renders with: one of the catalog's
(`cv_engine/domain/templates.py`) or `null` for the track's own. Allowed in every state,
as an edit is; the hash moves, so an approved or Ready document returns to draft and is
approved and rendered again. Choosing the template it has changes nothing. Content,
stamps, and files are kept. A new document starts with the user's `default_template`
(product-spec §15), copied when the first analysis creates it.

### `create_draft(application_id, expected_document_hash, provider, model?, reasoning_effort?)`

Operation, only while `content IS NULL`; `provider` is `openai`. Sends each section's
pool and guidance to `draft_resume` (product-spec §10), refuses facts outside the pool
or not canonical, lays facts out in pool order, and activates wording through review.
Writes `content` only while `document_hash == expected_document_hash`. A missing
rendering fails with `MISSING_FACT_RENDERING`.

### `update_document(application_id, If-Match, patch)`

Synchronous autosave. Patch: `claim_edits` (text, fact IDs, template),
`claim_removals`, `claim_additions` (section + text), `claim_orders` (full order per
section). Returns the new `document_hash`; mismatch is 409. Unauthorized free text is
saved as a pending claim with a reason. Headline and contacts are structural. Editing an
approved or Ready document returns it to draft.

### `regenerate_section` / `regenerate_claim`

Operations against `expected_document_hash`, a section or claim, and an optional
instruction (404 if unknown). They reword already-linked facts and do not choose new
ones. `regenerate_claim` with `keep_text` reviews the claim as written; it requires a
pending claim linked to at least one fact.

### Previews

`preview` (HTML) and `preview.pdf` render the current content marked as a draft, in
the document's template. No approval needed, nothing stored. 412 while `content IS NULL`.
`preview?template=<name>` (`track` for the track's own) shows the content in another
template without choosing it, for the template picker.

`GET /templates/{template}/sample?language=en|he` renders a fictional sample CV
(`rendering/samples/template-sample.json`) in one template, so Settings can show a
template before any CV exists. It reads no user's data.

## 15. Check and approval commands

### `check_document(application_id, expected_document_hash)`

Synchronous, no provider. Validates current content against its analysis and current
Knowledge, and stores `content_report`, `passed`, and `checked_basis`, also when it
fails. Content bound to another Application, analysis, or job text fails as
`document-binding-mismatch`. A validator crash stores nothing.

The report holds issues, evidence, and validator versions.

### `approve_document(application_id, expected_document_hash)`

1. Refuses a deleted Application, a hash mismatch, or `content IS NULL`.
2. If `approved_basis` and `checked_basis` already equal the basis, returns the existing
   approval unchanged.
3. Refuses with the first review reason (412).
4. Validates; under the document row lock stores the report and `checked_basis`, and —
   only if it passed — `approved_basis`, `approved_at`, and an audit record.

A failed check is `200` with `passed = false`.

## 16. Rendering commands

### `render_document(application_id, expected_document_hash)`

Operation. At queue time requires the hash, `preparation_state = approved` (else
`DOCUMENT_NOT_APPROVED`, 412), and no review reason. Execution revalidates, writes HTML,
renders the PDF with Playwright Chromium to a per-attempt path, and checks geometry,
page count, PDF/ATS text (coverage, and each date range extracted as one run), links,
direction, and filename metadata.

Activation locks the document and requires an unchanged hash and
`approved_basis == basis`; then it swaps the file paths, stamps `rendered_basis`, and
clears `last_render_error`. Only render activation writes `rendered_basis`.

A failure records `last_render_error` (reason plus hash) while the hash is unchanged,
never touches the active files, and leaves the document approved. Superseded files are
deleted best-effort.

### `export_recruiter_pdf(application_id)`

Refuses with `DOCUMENT_NOT_READY` (412) unless `ready`. Streams the PDF with a friendly
filename and the document hash as ETag.

### `export_decision_markdown(application_id)`

Markdown provenance export of the current document: analysis, dependent facts, content
report.

## 17. Knowledge commands

Facts are per user in PostgreSQL; each mutation is one transaction (architecture.md
§7.2). Another user's fact is 404. Statuses: `pending`, `canonical`, `deleted`.

### Reads

- `list_facts(status?)`: excludes `deleted` unless `status=deleted`.
- `show_fact(fact_id)`: one fact with its events, deleted included.
- `fact_history(fact_id?)`: lifecycle events.
- `list_fact_attachment_targets(fact_id?)`: Profiles and sections, with whether the fact
  is attached or pinned there. A deleted `fact_id` is 404.

### `create_pending_fact`

Creates a pending fact with a generated ID (client IDs refused). Input: source file,
meaning, renderings (`en` required, `he` optional), tags, provenance, `resume_style`,
optional dates, optional `replaces`, reason. With `replaces` it is a pending correction.

### `confirm_fact(fact_id)`

`pending -> canonical`. Requires `confirm: true`. Sets `confirmed_at` and advances the
source file's version. Confirming a replacement raises `FACT_SUPERSEDED` (§8) on
documents using the original.

### `edit_fact(fact_id, changes, confirm)`

*Not built.* Changes meaning, renderings, tags,
provenance, dates, `resume_style`, or link target in place; not the ID or source. A
canonical fact needs `confirm: true` and stays canonical. Deleted facts and empty edits
are refused. Appends a `fact_edited` event; dependent documents' basis moves.

### `delete_fact(fact_id)`

Confirmed, one-way move to `deleted` from `pending` or `canonical`. Always allowed;
dependent documents report `FACT_DELETED_REQUIRES_RESOLUTION` (§7). Submissions are
unaffected. A deleted fact is refused by `confirm_fact`, `attach_fact`, and
`confirm_and_use_fact`.

### `attach_fact(fact_id, profile, section, pin=false)`

Adds a canonical fact to a Profile section's pool, optionally pinned.

### `confirm_and_use_fact(fact_id, application_id, job_analysis_id, profile, section)`

One transaction: `pending -> canonical`, then attach to the section. Requires the
document to be built on `job_analysis_id`, whose Profile is `profile`. Writes no
document; the next `create_draft` can use the fact.

### `create_fact_from_claim(application_id, claim_id, ...)`

Creates a pending fact from a claim's exact text. Meaning, tags, and provenance are
supplied; a Hebrew document also needs the English rendering. The headline cannot
become a fact.

## 18. Tracking commands

### `submit_application(application_id, expected_document_hash, submitted_at, metadata)`

Records a send that already happened. Requires the hash, `preparation_state = ready`
with both files present (`DOCUMENT_NOT_READY`, 412), and no review reason. Copies the
HTML and PDF to submission storage with SHA-256, then in one transaction re-checks the
hash, stamps, and paths, inserts the Submission, moves `saved -> applied` if needed, and
appends events.

The Submission records content, `document_hash`, the Application's `job_text_hash`, file
paths and SHA-256s, `submitted_at`, and metadata. Any Submission locks the job text.

On an older analysis the result carries `DOCUMENT_ON_OLDER_ANALYSIS`. Multiple
submissions are allowed; they never change the document.

### `record_external_submission(application_id, submitted_at, metadata)`

Records a Submission with no content or files; same `saved -> applied` rule.

### `transition_recruitment_status(application_id, target_status, reason?, occurred_at?)`

Applies one allowed transition (§10). `applied` and disallowed targets are 409. The
current status is a no-op.

### `correct_recruitment_status(application_id, target_status, corrects_event_id, reason)`

Requires a reason and a status event of this Application (404 unknown, 409 foreign or
wrong kind). Appends a correction and updates status and terminal outcome.

### `set_next_action(application_id, next_action?, next_action_date?)`

Sets or clears the next action and date, appending an event.

## 19. Operation commands

### `get_operation(operation_id)`

The Operation read (§11).

### `cancel_operation(operation_id)`

Queued: `cancelled` immediately. Running: records `cancellation_requested_at`, then ends
`cancelled` without activating anything.

### `retry_operation(operation_id, Idempotency-Key?)`

Creates a new Operation with `retry_of_operation_id` and the original payload, model,
and effort. Terminal Operations only (409 otherwise). A document retry uses the current
`document_hash`. `MISSING_FACT_RENDERING` and `SOURCE_CHANGED` failures offer no retry.

### Idempotency

Async commands accept an optional `Idempotency-Key` (generated if absent), scoped per
Operation type and Application. The same key and payload returns the existing
Operation; a different payload is `IDEMPOTENCY_KEY_REUSED` (409).

## 19a. Settings commands

One Settings row per user, with `edit_version`.

### `read_settings()`

Returns settings, `edit_version` (ETag), whether a provider is configured, and the
model allowlist.

### `update_settings(If-Match, settings)`

Writable: `ui_theme`, `ui_density`, `ui_text_size`, `default_ai_model`,
`default_reasoning_effort`, `auto_generate_when_review_not_required`. Optimistic on
`edit_version` (409 on mismatch); the client keeps local edits and lets the user
reapply.

## 19b. Maintenance commands

Operator CLI only, across all users.

### `reconcile()`

`python -m cv_engine.admin reconcile`. Checks every Submission file against its SHA-256
(`payloads_checked`), every AI call's sanitized response against its hash
(`ai_calls_checked`), and the fact lifecycle against its event trail. Reports, never
repairs. `passed` is the conjunction of all parts.

### `inspect_orphans()`

`python -m cv_engine.admin inspect-orphans`. Lists Submission payloads in storage that
no row references and that are older than one hour (`ORPHAN_MIN_AGE`). Deletes nothing;
there is no reclaim command.

## 20. Queries

- **Application list** (`GET /applications`): filters `activity` (`open` | `closed` |
  `all`), `stage`, `recruitment_status`, `preset` (`needs_attention` = any review reason
  or warning; `ready_to_send` = `ready`; `active_interviews` = `recruiter_screen`
  through `offer`), `search`; `sort` (`updated` | `created` | `company` | `stage`);
  `limit` (1–200), `offset`. Rows carry the §9 projection and `is_closed`. The response
  carries `matched` and facet counts; each facet ignores its own filter. Deleted
  Applications are excluded.
- **Application detail**: §9 projection plus the Application, `job_posting`, latest
  analysis, `allowed_recruitment_transitions`, and timeline. Works for deleted
  Applications.
- **Duplicate check** (§12).
- **CVDocument**: ID, analysis ID, content and outline, language, dependent facts,
  `built_with`, `document_hash`, content report and `content_check`,
  `preparation_state`, `approved_at`, `last_render_error`, timestamps.
- **Document previews** (§14).
- **Operation** (§11).
- **Facts** (§17).
- **Settings** (§19a) and **health** (liveness and versions only for anonymous callers).

All queries return only the signed-in user's records, as DTOs, never rows or paths.

## 21. HTTP mapping

Everything maps to `/api/v1`; `openapi/openapi.json` lists the routes.

- Synchronous creation is `201`; an accepted Operation is `202` with `Location`.
- The document is at `/applications/{id}/document`, with `document_hash` as a strong
  ETag. Only `PATCH` takes it as `If-Match` (weak or malformed is 412); other document
  actions send `expected_document_hash` in the body.
- Settings use ETag `"settings-<edit_version>"` with `If-Match` on `PATCH`.
- CORS exposes `ETag`, `Location`, `Content-Disposition`, `Retry-After`, and allows
  `If-Match`, `Idempotency-Key`.
- Every route needs a session except `login` (§23) and health.

## 22. HTTP outcomes

| Status | Meaning |
| --- | --- |
| `200` | query, synchronous update, or a successful outcome such as a failed check or reconciliation |
| `201` | synchronous creation |
| `202` | accepted Operation with `Location` |
| `401` | no valid session (`AUTHENTICATION_REQUIRED`), failed sign-in (`INVALID_CREDENTIALS`), wrong current password (`REAUTHENTICATION_FAILED`) |
| `403` | refused Origin or Host (`ORIGIN_NOT_ALLOWED`); never for another user's record |
| `404` | unknown record (`UNKNOWN_RECORD`), including another user's record and a document not yet created |
| `409` | state conflict: hash, notes, or settings mismatch; deleted Application; disallowed transition; job text changed or locked; idempotency-key reuse |
| `412` | precondition, blocker, review reason, intake refusal, lineage or Knowledge refusal |
| `413` | body too large |
| `422` | request does not match the schema (`REQUEST_VALIDATION_FAILED`) |
| `429` | sign-in rate limit (`RATE_LIMITED`), with `Retry-After` |
| `500` | infrastructure failure |
| `503` | a required collaborator is not configured |

Errors are Problem Details (`application/problem+json`) with `type`, `title`,
`status`, `code`, `detail`, and optional `context`; never a stack trace, path, provider
response, or secret.

`code` defaults to the refusal class in upper snake case (`STATE_CONFLICT`,
`PRECONDITION_FAILED`, `KNOWLEDGE_REJECTED`, `LINEAGE_BROKEN`, `VALIDATION_BLOCKED`,
`APPLICATION_INTAKE_INVALID`, ...). Named codes:

```text
DOCUMENT_CHANGED                    DOCUMENT_NOT_APPROVED
DOCUMENT_NOT_READY                  MISSING_FACT_RENDERING
DUPLICATE_ACKNOWLEDGEMENT_REQUIRED  IDEMPOTENCY_KEY_REUSED
PENDING_FACT_REQUIRES_RESOLUTION    FACT_DELETED_REQUIRES_RESOLUTION
```

Review reasons, warnings, and validation issues are projection data; they become a
refusal only when a blocked command is attempted.

## 23. Account commands

Product rules: product-spec.md §22. Mechanisms and limits: architecture.md §18.

Routes are under `/api/v1/auth`, JSON bodies, Origin-checked mutations, session in an
opaque cookie only, `Cache-Control: no-store`. `login` and `logout` need no session.

### `login(email, password)`

`POST /auth/login`. Rate limited first (`429 RATE_LIMITED` with `Retry-After`). On
success creates a session, sets its cookie, returns `me`, and revokes any session the
request presented; an outdated password hash is upgraded. Any failure is
`401 INVALID_CREDENTIALS` with the same body and comparable timing, logged without the
password.

### `logout()` / `logout_all()`

`POST /auth/logout` revokes the current session and clears the cookie (`204` even with
no session). `POST /auth/logout-all` revokes every session of the user (`204`).

### `me()`

`GET /auth/me`: user ID, email, `created_at`; `401` without a session.

### `change_password(current_password, new_password)`

`POST /auth/change-password`. Wrong current password: `401 REAUTHENTICATION_FAILED`.
Policy violation: `422 PASSWORD_POLICY_FAILED`. Success revokes other sessions and
rotates the current one.

No route deactivates or deletes an account.

### Operator commands

`create-user`, `set-password`, `import-knowledge`, and `export-knowledge` are CLI
commands (architecture.md §18.7). `set-password` revokes every session of the user.

### Codes

```text
AUTHENTICATION_REQUIRED     INVALID_CREDENTIALS       REAUTHENTICATION_FAILED
PASSWORD_POLICY_FAILED      RATE_LIMITED
```
