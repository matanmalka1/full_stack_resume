# Decision: one mutable CV document per Application

Status: implemented (2026-09-28). The specifications listed in §8 describe this model;
the three-wave execution plan is closed and lives in Git history.

## 1. Why

Approval currently freezes the draft into an immutable ApprovedRevision and closes the
WorkingDraft. Returning to editing therefore means creating a new draft from a revision
(an Operation, a `parent_revision_id`, a second concurrent "ready" milestone), and the
wizard cannot offer a plain way back from Ready to the draft step because no draft exists.

Almost everything the engine produces is regenerable. What is not regenerable is what left
the system: the posting as captured and the CV actually sent. The new model freezes only
that. There is no data to migrate and no backward compatibility to keep.

## 2. The model

```text
JobSnapshot (immutable)  ->  JobAnalysis (immutable, one row per analyze)
                                   |
                                   v
CVDocument (mutable, one per Application)
  analysis_id
  selection                     -- was SelectionPlan.plan_json (§5)
  content                       -- was WorkingDraft.source_json; NULL until generated
  built_with                    -- profile_version, selection_policy_version (§5)
  document_hash                 -- stored: hash(selection, content, analysis_id)
  content_report, checked_basis, passed
  approved_basis, approved_at
  rendered_basis, html_path, pdf_path, last_render_error

Submission (immutable)  content, document_hash, job_snapshot_id,
                        html_path + html_sha256, pdf_path + pdf_sha256
```

**Basis.** `basis = hash(document_hash, facts_hash)`, where `facts_hash` is the hash of
the current canonical content of every fact the document depends on (selection fact IDs
∪ claim fact IDs). The basis is computed on read from the document and the loaded
Knowledge; only the stamps (`checked_basis`, `approved_basis`, `rendered_basis`) are
stored. Any change to the document or to a fact it depends on changes the basis, however
the fact changed.

Derived states (a NULL stamp never equals the basis):

| State | Condition |
| --- | --- |
| draft | `approved_basis IS NULL OR approved_basis != basis` |
| approved | `approved_basis == basis AND (rendered_basis IS NULL OR rendered_basis != basis)` |
| ready | `rendered_basis == approved_basis == basis` |

The content report is current only while `checked_basis == basis`; otherwise it is shown
as outdated.

## 3. Decisions

1. **One document hash.** `document_hash = hash(selection, content, analysis_id)`. File
   integrity of a Submission is a separate storage checksum per file (decision 7).
2. **JobAnalysis is immutable.** Each analyze writes a new row; its ID is its identity.
3. **The document is pinned to its analysis.**
   - The first analysis of an Application, when no document exists, creates the document
     with a deterministic selection and no content.
   - Later analyses never change the document; they raise the "older analysis" warning.
   - `build_from_analysis` is an explicit action that replaces `analysis_id`, selection and
     content.
4. **Approve** runs content validation and approves in one synchronous action, stamping
   `checked_basis` always and `approved_basis` on success. Approving when `approved_basis`
   already equals the basis returns the existing approval without rewriting `approved_at`
   or appending audit records.
5. **Render** validates content, renders to a unique per-attempt path, and checks the output
   (geometry, page count, ATS text, links). Activation locks the document row and requires
   `approved_basis == basis` and `document_hash == expected_document_hash`; only then it
   swaps `html_path`/`pdf_path`, stamps `rendered_basis` and clears `last_render_error`.
   A failure records `last_render_error` only while `document_hash` still equals the
   expected hash; otherwise only the Operation keeps the failure. Active files and
   `rendered_basis` are never touched by a failure. Superseded files (after success) and
   failed-attempt files are deleted best-effort. Render activation is the only writer of
   `rendered_basis`. Readiness does not depend on a render version.
6. **Fact changes need no write-side invalidation.** Because the basis includes the facts
   the document depends on, a fact deleted, replaced, demoted or edited — through the
   journal or by hand in `base/` — drops the document out of approved/ready on the next
   read. The PDF download of a Ready document checks the basis at request time. The
   knowledge mutation journal writes nothing to the document.
7. **Submission records a send that already happened** (it carries a submission time). It
   locks the document row, requires `rendered_basis == approved_basis == basis`, and copies
   the content plus the rendered files to submission-owned paths with a SHA-256 per file.
   It is not a validation gate. It references the immutable JobSnapshot (FK `RESTRICT` plus
   the existing immutability-trigger pattern). External submissions keep their current
   shape.
8. **Operations.** Analysis, AI selection proposals, AI draft generation/regeneration and
   render are asynchronous. Manual edits, deterministic selection changes, approve and
   submit are synchronous.
   - An async operation that mutates an existing document (AI selection proposal,
     regeneration, render) carries `expected_document_hash`; a mismatch at activation
     discards the result.
   - Document creation relies on the one-document-per-Application unique constraint.
   - Analysis is bound to its input JobSnapshot, not to a document.
   - Operations keep the input identities they need to execute, retry and pin, but
     draft-producing operations do not recheck input freshness at activation: their output
     is unapproved, and approve/render validate against the current authoritative context
     (facts and their eligibility, profile, policy, evidence).
9. **PreparationState** becomes `needs_analysis`, `ready_to_draft` (document has a
   selection but no content), `draft_in_progress`, `approved`, `ready`.
   `ready_for_approval` becomes the `approve` capability. `needs_review` becomes a
   blocker/reason overlay, not a stage.
10. **Not built:** a "last ready PDF" fallback, attestation/approval event tables, history
    of approvals that were never submitted, a reconciliation blocker for hand-edited facts
    (the basis already covers it).

## 4. Tables

### Affected

| Table | Decision | Mutable | Kept as evidence |
| --- | --- | --- | --- |
| `job_snapshots` | keep | no | yes |
| `job_analyses` | keep | no | no |
| `selection_plans` | delete; fields reallocated (§5) | — | — |
| `working_drafts` | replace with `cv_documents` | yes | no |
| `approved_revisions` | delete | — | — |
| `decision_records` | delete (one row per ApprovedRevision) | — | — |
| `validation_runs` | delete; report lives on the document | — | — |
| `artifacts` | narrow to `provider_response`; `resume_pdf`, `resume_html`, `resume_markdown`, `claim_manifest`, `working_draft_snapshot` removed | no | yes (AI provenance) |
| `artifact_versions` | narrow as above; `revision_id` column removed | no | yes |
| `payload_write_leases` | keep for intake, provider-evidence and Submission payloads (state-and-use-cases.md §18); approval, history and render stop using it | yes | no |
| `operation_outputs` | keep for provider evidence; render no longer registers artifact outputs | yes | no |
| `operation_resource_leases` | keep unchanged (`application_mutation`, `render_browser`, `ai`) | yes | no |
| `idempotency_receipts` | keep for operation replacement; approval stops using it (decision 4) | yes | no |
| `operations` | keep; operation types follow decision 8 | yes | no |
| `audit_records` | keep; entity types move from revision/draft to document | no | yes (history) |
| `submissions` | restructure per decision 7 (drop `approved_revision_id`, `artifact_version_id`) | no | yes |
| `knowledge_mutation_journal` | keep; its `selection_plan` DB action becomes a document selection update (decision 6 adds nothing) | yes | no |

### Unaffected (reviewed)

- `applications`: Application identity, recruitment status, soft delete.
- `recruitment_events`: recruitment status history.
- `fact_events`: fact lifecycle audit.
- `app_settings`: user settings.

## 5. SelectionPlan allocation

| Field | New owner | Reason |
| --- | --- | --- |
| `plan_json` (candidates, selected, pinned, excluded, tag coverage, `emphasis_override`) | `cv_documents.selection` | The user edits it before and after content exists (fact selection screen, `apply_selection_change`). It is part of the document, so it is part of the hash. |
| `job_analysis_id` | `cv_documents.analysis_id` | Decision 3. |
| `profile_version`, `selection_policy_version` | `cv_documents.built_with` | Drives a "built with an older profile/policy" warning. Gates validate against the current values. |
| `track_emphasis_dependencies` | deleted | Track comes from the analysis; effective emphasis is in `selection`. Both are already inside the hash. |
| `candidate_context_version`, `candidate_context_hash` | deleted | Fed `FACT_CHANGED` staleness; the basis replaces it (decision 6). |
| `version_number` | deleted | No plan history. |

## 6. Reason codes

| Code | Today | New |
| --- | --- | --- |
| `JOB_SNAPSHOT_CHANGED` | stale | warning, folded into "document built on an older analysis" |
| `ANALYSIS_REPLACED` | stale | same warning (decision 3) |
| `SELECTION_PLAN_REPLACED` | stale | deleted: the selection is part of the document |
| `FACT_CHANGED` | stale | basis mismatch: approval and report become outdated (decision 6) |
| `PROFILE_CHANGED`, `POLICY_CHANGED` | stale | warning from `built_with` |
| `DRAFT_EDITED_AFTER_VALIDATION` | stale | basis mismatch: `checked_basis != basis` |
| `FACT_SELECTION_UNRESOLVED` | review | deleted: the document is created with a selection |
| `PENDING_FACT_REQUIRES_RESOLUTION` | review | blocker, unchanged |
| `FACT_DELETED_REQUIRES_RESOLUTION` | review | blocker, computed on selection ∪ claims, the same set as `facts_hash` |
| `KNOWLEDGE_RECONCILIATION_REQUIRED` | review | blocker, unchanged |
| `READY_REVISION_FOR_OLDER_SNAPSHOT`, `..._ANALYSIS` | warning | merged into the "older analysis" warning |
| `READY_REVISION_FOR_OLDER_SELECTION_PLAN` | warning | deleted |
| `FACT_SUPERSEDED`, `FACT_KNOWN_INCORRECT` | warning | warning, on the document |
| `FACT_DELETED` | warning | deleted: a live document with a deleted fact gets the blocker instead |
| `NEXT_ACTION_OVERDUE` | warning | unchanged |

## 7. Confirmed by the user

- **Decision 6 replaces write-side invalidation with a read-side basis.** It covers facts
  edited by hand in `base/`, which journal-driven invalidation cannot see, and it removes
  the journal step instead of adding a second mechanism.
- **`ready_to_draft` means "document without content"** (decisions 3 and 9).

- **Implementation details fixed in Wave 1** (2026-09-28): `document_hash` is also the
  document's concurrency token and ETag (no `edit_version`); `check_document` exists as a
  command separate from `approve`; `build_from_analysis` clears content and every stamp;
  the warnings are `DOCUMENT_ON_OLDER_ANALYSIS`, `PROFILE_CHANGED` and `POLICY_CHANGED`;
  `facts_hash` covers every field of a fact, including its status, except `source_file`.

- **Decided in Wave 3** (2026-09-28): the document's candidate rows carry no ranking
  terms (requirement tier, profile and emphasis scores, keyword hits, gap substitute).
  The engine still ranks by them; the fact rows explain themselves by the requirements
  each fact is evidence for. An Operation's `output_type` is the closed set
  `job_analysis`, `cv_document`, `provider_response`.

## 8. Specification sections to rewrite

- `spec/state-and-use-cases.md`: §2–§9 (entities, context, PreparationState,
  WorkingDraftState, staleness, review, warnings, projection), §11 and §19 (Operation
  lifecycle), draft commands, §15–§16 (approval, rendering), §18 (submission), query
  contracts and revision history.
- `spec/product-spec.md`: validation, approval, Ready and the no-pause flow (§10–§11).
- `spec/architecture.md`: storage layout, payload registration, leases, §7.2 journal
  actions.
- `spec/test-and-acceptance-plan.md`: golden artifacts, pipeline scenario, state scenarios.
- `CLAUDE.md`: the immutable-records paragraph, last, to match the rewritten specs.
