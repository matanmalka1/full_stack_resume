import type { ApplicationDetail, ApplicationListItem } from "@/api/contracts";

/* The same rule the server closes a record by (`application_is_closed`): an outcome on
   record, or a status that ends the process. The detail read does not carry the board's
   `is_closed`, so it is read off the two fields it is made of. */
const CLOSED_STATUSES: ReadonlySet<string> = new Set(["rejected", "withdrawn", "closed"]);

export const isApplicationClosed = (detail: ApplicationDetail): boolean =>
  detail.terminal_outcome != null || CLOSED_STATUSES.has(detail.recruitment_status);

/* The record as the board's list names it, built from the detail read this screen
   already holds. The board's record commands - its menu, its close and delete
   confirmations, its details dialog - take a list item; this screen offers the same
   commands, so it hands them the same shape rather than growing copies of them that
   take a detail. Every field is the projection's own, renamed where the two reads nest
   it differently; nothing is invented. */
export const listItemFromDetail = (detail: ApplicationDetail): ApplicationListItem => ({
  ...detail.application,
  active_operation: detail.active_operation ?? null,
  approved_at: detail.approved_at ?? null,
  available_actions: detail.available_actions,
  blocked_actions: detail.blocked_actions,
  content_check: detail.content_check,
  document_analysis_id: detail.document_analysis_id ?? null,
  document_hash: detail.document_hash ?? null,
  document_id: detail.document_id ?? null,
  is_closed: isApplicationClosed(detail),
  job_text_hash: detail.job_text_hash,
  last_render_error: detail.last_render_error ?? null,
  latest_analysis_id: detail.latest_analysis_id ?? null,
  latest_operation: detail.latest_operation ?? null,
  preparation_state: detail.preparation_state,
  recommended_action: detail.recommended_action ?? null,
  recruitment_status: detail.recruitment_status,
  review_reasons: detail.review_reasons,
  terminal_outcome: detail.terminal_outcome ?? null,
  warnings: detail.warnings,
});
