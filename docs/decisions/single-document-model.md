# Decision: one mutable CV document per Application

Status: implemented (2026-09-28). The specifications describe this model and are
authoritative; this record keeps why, what was not built, and how the old model maps onto
the new one. The three-wave execution plan is closed and lives in Git history.

Superseded in part (2026-10-01). The tables this record kept for provider evidence are
gone: `artifacts`, `artifact_versions`, the `provider_response` output type and inactive
Operation outputs were replaced by the append-only AI call log (`ai_calls`,
architecture.md §11), and `operation_resource_leases` by partial unique indexes on
`operations` (architecture.md §10). `payload_write_leases` no longer exists either. The mapping table in §4 records the state at
2026-09-28 and is left as it was.

## 1. Why

Approval currently freezes the draft into an immutable ApprovedRevision and closes the
WorkingDraft. Returning to editing therefore means creating a new draft from a revision
(an Operation, a `parent_revision_id`, a second concurrent "ready" milestone), and the
wizard cannot offer a plain way back from Ready to the draft step because no draft exists.

Almost everything the engine produces is regenerable. What is not regenerable is what left
the system: the posting as captured and the CV actually sent. The new model freezes only
that. There is no data to migrate and no backward compatibility to keep.

## 2. The model

Specified in [`state-and-use-cases.md`](../spec/state-and-use-cases.md) §3 (the CVDocument,
its basis and derived states), §4 (PreparationState) and §6 (why nothing goes stale). This
record does not restate it.

## 3. Decisions

Decisions 1–9 are specified in [`state-and-use-cases.md`](../spec/state-and-use-cases.md);
the numbers stay because §4–§6 below cite them.

1. One document hash — §3.
2. JobAnalysis is immutable — §13.
3. The document is pinned to its analysis — §13, §14 (`build_from_analysis`).
4. Approve — §15.
5. Render — §16.
6. Fact changes need no write-side invalidation — §6.
7. Submission records a send that already happened — §18.
8. Operations — §11.
9. PreparationState — §4.

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
| `idempotency_receipts` | delete (migration `0003`): approval stops using it (decision 4) and operation replacement is gone, so nothing wrote it | — | — |
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

Superseded by [`ai-owned-selection.md`](ai-owned-selection.md): the document no longer
holds a selection, and `selection_policy_version` is gone.

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
