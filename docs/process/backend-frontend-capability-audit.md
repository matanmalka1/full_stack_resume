# Backend/Frontend Capability Audit — 2026-09-10

Ad-hoc audit requested in chat: which backend capabilities exist without a frontend
consumer. Recorded here so the findings aren't re-derived from scratch next time. Not a
task checklist — no action items follow from this unless someone decides to act on one.

## Method

1. Extracted every path in `openapi/openapi.json` (56 total) and grepped
   `frontend/src/api/*.ts` for actual callers of each.
2. For the ones with no caller, read the backend code that serves them to understand
   intent rather than guessing from the route name.
3. Went one layer deeper: listed every public method on the application-service classes
   under `cv_engine/application/services/` and searched the whole non-test codebase for
   callers, to catch capabilities that never got an API route at all (not just ones with
   a route nobody calls).
4. Cross-checked the `/api/v1/settings` field set (`SettingsResponse` /
   `UpdateSettingsRequest`) against `frontend/src/features/settings/components/SettingsForm.tsx`.

## Findings

### `GET /api/v1/applications/{id}/decision` — has a route, no frontend caller, by design

Returns the persisted `DecisionRecord` for an application's most recent approval:
`structured` (track/profile/emphasis/language/fit/gaps/selected_fact_ids/omitted_facts/
derived_statements/accepted_gaps/user_overrides/...) plus a human `summary` and
`created_at`. The record is written once per approval, in
`DraftApproval.approve_draft` (`cv_engine/application/services/drafts/approval.py`), not
at classification-decision time — so it doesn't exist until an application has at least
one `ApprovedRevision`.

`docs/spec/state-and-use-cases.md:606-609` documents this explicitly: `export_decision_
markdown` (used by the revision screen, via `GET /approved-revisions/{id}/decision-
markdown`) is "the primary human export"; this endpoint is the stated diagnostic-JSON
companion, addressed by application rather than by a specific revision. Same underlying
record as the Markdown export, different shape and a different key (latest-for-
application vs. one-named-revision). Not dead code, not a spec conflict — decided not to
build a UI for it (2026-09-10 chat).

### `GET /api/v1/facts/{fact_id}/history` — has a route, no frontend caller, redundant

`GET /api/v1/facts/{fact_id}` (`read_fact`, used everywhere facts are shown) already
returns `events` inline. This dedicated per-fact history endpoint duplicates that. Low
priority either way: nothing is missing from the UI, the backend just carries one read
path more than the frontend needs.

### `GET /api/v1/health` — has a route, no frontend caller, not meant to have one

Instance identity/version + knowledge versions. Operational/diagnostic surface (used by
`scripts/cloud-dev.sh`'s health check), not user-facing product information.

### `DraftEditing.edit_claim` — no API route at all, intentionally

`cv_engine/application/services/drafts/editing.py`. A full single-claim edit + re-
validate command, called directly at the service layer in tests
(`tests/test_api_working_drafts.py:271`), never through HTTP. The test's own docstring
says why: it simulates "a maintenance path or a second Web session" writing to a draft
out-of-band, to test optimistic-concurrency (stale-ETag) refusal. The Web UI's actual
single-claim edit path is the generic `PATCH /api/v1/working-drafts/{id}` structured
patch (`update_working_draft`), which is used. `edit_claim` is a lower-level write path
kept deliberately off the API surface, not a missing frontend feature.

### `DraftGeneration.draft` and `RenderingService.ready_report` — no non-test callers, and that's fine

Both are one-line compositions of methods that are otherwise called separately (`draft`
= `prepare` + `activate`; `ready_report` = `ready_qualification(...).validation`). Used
extensively as synchronous test shortcuts (e.g. `services.drafts.draft(...)` across
`tests/test_chain_integrity.py`, `tests/test_state_projection.py`, etc.) for state the
real system builds through the async Operation/worker path. Test-only convenience
wrappers, not unused product capability.

### Settings — full parity

Every field `PATCH /api/v1/settings` accepts (`auto_generate_when_review_not_required`,
`ai_enabled_override`, `default_execution_mode`, `default_ai_model`,
`default_reasoning_effort`, `ui_density`, `ui_text_size`) is read and written in
`SettingsForm.tsx`. The infra-level `Setting(...)` entries in
`cv_engine/runtime/config.py` (`CV_DATABASE_URL`, `CV_OBJECT_STORE`, S3 config, etc.) are
a different, intentionally `.env`-only layer — never meant to be user-editable, so their
absence from the Settings UI isn't a gap either.

## Bottom line

53 of 56 REST endpoints are used. The 3 that aren't are each accounted for (one
deliberate diagnostic-only route, one redundant read path, one ops endpoint). One layer
deeper, at the application-service boundary, nothing turned up beyond what's already
explained above — no capability found with real product value and zero path to it.
