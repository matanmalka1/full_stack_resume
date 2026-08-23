# M3 Acceptance — Application API Vertical Slice

Status: **M3 closed — all seven §5.4 acceptance criteria passed** (2026-08-23)

Milestone: `docs/v2/spec/implementation-plan.md` §5.1–§5.4

Implementation head before this documentation boundary: `f6d5df2`.

This record is frozen at M3 close. It records what the final gate proved; later
milestones do not update it.

## Closing changes

| Commit | Boundary |
| --- | --- |
| `962a818` | TODO 22: order `latest_decision` by immutable artifact version, including a same-timestamp repository/API regression |
| `12320e2` | Complete the remaining acceptance matrices and redact infrastructure/provider prose from Problem Details |
| `f6d5df2` | Close the Stage G static typing failures without changing the runtime contracts |

The earlier Stage A–G commits and their accepted evidence remain recorded in
`docs/v2/m3-remaining.md`; they are not recopied here.

## Acceptance-to-assertion map

The map names assertions, not merely files. Closely related requirements deliberately
share tests where one composed path proves more than isolated examples would.

| Requirement | Direct proof |
| --- | --- |
| §5.1 happy path and state after every step | `test_the_full_api_journey_reaches_ready_offline`: Create/Analyze/Draft/Edit/Validate/Approve/Render/Ready and exact PDF download; asserts PreparationState and WorkingDraftState at every transition and uses Analyze's returned SelectionPlan ID directly |
| §5.2 review path | `test_the_review_journey_resolves_once_and_reaches_ready`: successful NeedsReview Operation, one apply-decisions submission, replacement immutable analysis/plan, then Draft/Validate/Approve/Render/Ready |
| §5.3 editor safety | `test_a_patch_with_the_current_etag_saves_and_returns_the_next_one`, `test_free_text_no_fact_authorizes_is_kept_as_a_pending_claim`, `test_a_failed_validation_is_a_successful_outcome_with_its_run_recorded`, `test_captured_claim_becomes_a_usable_fact_end_to_end`, and `test_an_edit_after_validation_makes_that_run_unusable_for_approval` |
| §5.4 rendering failure | `test_a_failed_render_leaves_the_approved_revision_exactly_as_it_was` and `test_retrying_a_failed_render_creates_a_new_operation`: failure is Operation data, approval is unchanged, retry is a new Operation, and only its exact active artifacts qualify the same revision as Ready |
| §5.5 preparation half | `test_ready_milestone_survives_a_new_draft_for_the_same_context`, `test_new_snapshot_makes_ready_historical_and_requires_analysis`, and `test_new_analysis_makes_parallel_draft_stale_without_erasing_ready_history` |
| Two autosaves / CLI versus Web | `test_a_second_save_with_the_same_etag_is_a_conflict_that_changes_nothing` and `test_cli_edit_wins_before_a_web_autosave_with_the_stale_etag` assert the loser receives 409 and does not overwrite the winner |
| Analyze/generate/render/approve idempotency and changed payload | `test_reusing_an_idempotency_key_returns_the_one_operation_it_created`, `test_generation_reuses_one_operation_for_one_idempotency_key`, `test_an_idempotency_key_returns_the_first_render_instead_of_a_second`, `test_approval_idempotency_returns_the_exact_original_revision`, and the changed-payload assertions in `test_the_same_key_returns_the_same_revision_and_a_changed_payload_is_reuse` / `test_sqlite_operation_rejects_idempotency_key_with_another_payload` |
| Foreground versus worker | `test_foreground_executor_and_worker_race_one_operation_without_duplicate_execution` runs the two concrete hosts concurrently and counts exactly one handler execution |
| Cancellation, SOURCE_CHANGED, retry, and output existence | `test_cancel_and_manual_retry_keep_the_old_operation_immutable`, `test_source_changed_is_checked_before_execution_and_again_before_activation`, `test_a_cancelled_run_keeps_its_completed_output_as_inactive_evidence`, `test_a_source_that_moves_after_execution_keeps_the_output_as_inactive_evidence`, and `test_a_render_stopped_between_the_phases_keeps_registered_inactive_outputs`; every preserved output resolves to a registered record and remains inactive |
| Security matrix | Missing/foreign Origin, no-wildcard CORS, one development allowlist, 2 MiB body limit, traversal encodings, symlink escape, unregistered artifact, hash mismatch, and Problem Details redaction are asserted in `test_api_foundation.py` and `test_api_artifacts.py` |
| Outcomes as data | `test_needs_review_is_a_successful_outcome_carrying_both_records`, `test_a_failed_validation_is_a_successful_outcome_with_its_run_recorded`, and `test_a_failed_render_leaves_the_approved_revision_exactly_as_it_was` |
| Routers contain no business logic | `tests/test_architecture.py` derives and enforces API layer imports and router restrictions; final result 10/10 |
| Explicit command sources | `test_commands_require_owned_explicit_sources_and_cli_resolves_latest` plus the foreign-source HTTP refusals; `latest` remains a query/CLI compatibility concern |

## AI §6 map

| Requirement | Direct proof |
| --- | --- |
| Five task contracts, recursive strict schemas, task-specific parsing | `test_every_contracted_task_has_exactly_one_output_model`, five cases of `test_each_task_sends_a_strict_schema_and_parses_its_own_proposal`, and `test_a_nested_proposal_model_is_reached_by_the_strict_walk` |
| Semantic support beyond IDs | `test_a_valid_fact_id_with_strengthened_wording_fails_the_operation`, `test_a_fact_outside_the_claims_own_support_is_refused`, and `test_a_proposal_cannot_add_experience_that_is_not_in_the_facts` |
| Refusal, invalid output, no fallback | `test_a_refusal_is_a_provider_refusal_carrying_its_own_evidence`, invalid-output parametrization, `test_a_provider_failure_never_produces_a_deterministic_result`, and `test_ai_mode_with_no_provider_configured_is_an_explicit_refusal` |
| Sanitized registered raw response and provenance | `test_the_preserved_response_is_the_sanitized_one_and_its_hash_matches`, `test_sanitization_removes_secret_keys_at_any_depth`, `test_a_successful_run_registers_the_sanitized_response_with_full_provenance`, and `test_provenance_records_provider_model_usage_latency_and_response_id` |
| Stateless/minimal context | `test_each_task_receives_only_its_own_context`, `test_the_provider_receives_the_job_text_and_not_the_whole_fact_store`, and `test_selection_context_carries_the_profile_pool_and_not_every_fact` |
| Retry policy | One transient retry, persistent-transient cap, non-transient parametrization, unsupported-claim call count, stale-conflict zero calls, and stale-source one-call assertion |
| Five prompt-injection fixtures | Five cases of `test_injected_job_text_changes_no_policy_owned_result`, with companion schema and invented-experience refusals; the baseline test proves the policy comparison can fail |

The manual live OpenAI smoke was not run. It remains an M6 §8.2 release item.

## Final gate

Interpreter: `/Users/matanmalka/Projects/resume_python-v2/.venv/bin/python`, Python
3.14.2; pytest 9.1.1.

| Gate | Result |
| --- | --- |
| API journey | **2 passed** |
| Architecture | **10 passed** |
| AI focused | **65 passed** |
| Golden browser selection | **1 passed, 1 deselected** |
| Full non-browser | **439 passed, 4 deselected** |
| Browser-complete, `CV_REQUIRE_BROWSER=1` | **443 passed** |
| Ruff check / format | clean; 149 files formatted |
| Pyright | **0 errors, 0 warnings, 0 informations** after repairing the 10 Stage G typing errors found by the first final run |
| OpenAPI / TypeScript | regenerated after `npm ci`; no diff in `openapi.json`, `types.ts`, or `package-lock.json`; npm reported 0 vulnerabilities |
| `git diff --check` | passed |

### Count reconciliation

The opening HEAD `d6dec85` collected 435 non-browser tests plus 4 browser tests. That is
one above Stage F's recorded 434/438 because TODO 21 added exactly one regression in
`test_chain_integrity.py`. H added exactly four test items: the review journey,
generation idempotency, CLI/Web edit contention, and foreground/worker contention.
Therefore 435 + 4 = 439 non-browser and 439 + 4 = 443 browser-complete. Both final
results match exactly; no test was removed.

The 135-case acceptance focused run decomposes as 22 foundation + 2 journey + 27
working-draft + 54 Operations + 30 artifacts. The initial prediction used the Stage A
foundation count of 19; the apparent +3 was reconciled to the three Stage F guards,
which made the correct current foundation count 22.

## Offline CLI evidence

The real CLI ran with `OPENAI_API_KEY` removed against fresh isolated Workspace
`/var/folders/rt/yglsrkgn3zd05xb_fw2l4y980000gn/T/tmp.IrhqhdkmWN/m3-offline-workspace`,
using `--workspace` only:

`ingest → analyze → draft → validate → approve → render → ready → reconcile`

- Ready passed all six top-level groups; the render was one page with ATS claim coverage 1.0.
- Reconcile passed with exactly five artifact versions and no problems.
- ValidationRun `7faedfd0-033f-492c-b021-9e7bfee42220` is the exact ID stored on ApprovedRevision `b085b29e-3514-4645-a2dc-b7787135a169`.
- Decision provenance is `actor_type=user`, `client=cli`, `command=approve_draft`.
- The DecisionRecord language is `en`; decision Markdown contains a populated Language line.
- Artifact types are exactly `claim_manifest`, `resume_html`, `resume_markdown`, `resume_pdf`, and `visual_evidence`.
- No `provider_response` exists and no OpenAI key was required.

## Explicit deferrals and counterweight

- M5 owns §5.5's submission of an older qualified revision/PDF and its historical-context warning. Only the preparation half was required and closed here.
- M6 §8.2 owns the manual live OpenAI smoke. It is deliberately absent from automated M3 CI.
- TODO 23 remains cleanup: the golden-hash test is browser-marked and excluded from the default non-browser selection. It did not block M3 and was not reorganized.
- No control was retired at M3 close. The remaining controls all guarded active failure modes during this milestone; the two empty exception sets were explicitly ineligible.

M4 was not started.
