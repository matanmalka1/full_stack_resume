import type { ClassificationDecisions } from "@/api/analyses";
import type { ApplicationDetail, Reason } from "@/api/contracts";

/* Which review reasons the preparation screen decides itself, and what "decided" means.

   Presentation over codes the projection literally sends. Which reasons exist, and
   whether `apply_analysis_decisions` is available at all, stay the projection's answer;
   this only says which of them have a control here.

   It lives in the model rather than beside the form because four places ask it - the
   Application's tab badge, the preparation tab's own badge, the decision panel's
   heading, and the checklist in its action bar - and a count worked out four times is a
   count that eventually disagrees with the controls it describes. */

export const CLASSIFICATION_REASON = "MATERIAL_CLASSIFICATION_AMBIGUITY";

export const FIT_REASON = "LOW_FIT_REQUIRES_ACCEPTANCE";

/* Its own reason with its own control, and deliberately not the fit checkbox's. The two
   were one entry here, which made the fit acceptance claim to answer a hard gap: that
   acceptance is recorded on the analysis, while a gap acceptance is recorded per
   requirement on the SelectionPlan, and the server clears this reason only for the
   latter. Marking the fit therefore re-derived the analysis and left the blocker exactly
   where it was. */
export const GAP_REASON = "HARD_GAP_REQUIRES_DECISION";

export const INCOMPLETE_ANALYSIS_REASON = "ANALYSIS_INCOMPLETE";

/* A `Record` over exactly the codes this screen owns, so a review reason added to the
   backend falls through to being named as belonging elsewhere instead of quietly
   acquiring an unrelated control. */
const REVIEW_REASONS_THIS_SCREEN_OWNS: Record<string, true> = {
  [CLASSIFICATION_REASON]: true,
  [INCOMPLETE_ANALYSIS_REASON]: true,
  [FIT_REASON]: true,
  [GAP_REASON]: true,
};

/* Asked of the table above, so "this decision has a control" stays one fact in one
   place. */
export const resolvedByReviewDecision = (reason: Reason): boolean =>
  reason.allowed_resolution_actions.includes("apply_analysis_decisions") &&
  Object.hasOwn(REVIEW_REASONS_THIS_SCREEN_OWNS, reason.code);

export interface OpenDecisions {
  classification: boolean;
  fit: boolean;
  gaps: boolean;
  incompleteAnalysis: boolean;
}

/* Which decisions the projection is asking for right now. A gap decision needs the plan
   it would be recorded against: with no active SelectionPlan the projection is asking
   for a different reason with a different action. */
export const openDecisions = (detail: ApplicationDetail): OpenDecisions => {
  const mine = detail.review_reasons.filter(resolvedByReviewDecision);

  return {
    classification: mine.some((reason) => reason.code === CLASSIFICATION_REASON),
    fit: mine.some((reason) => reason.code === FIT_REASON),
    gaps: detail.active_selection_plan_id != null && mine.some((reason) => reason.code === GAP_REASON),
    incompleteAnalysis: mine.some((reason) => reason.code === INCOMPLETE_ANALYSIS_REASON),
  };
};

export const openDecisionCount = (open: OpenDecisions): number => Object.values(open).filter(Boolean).length;

export const emptyDecisions: ClassificationDecisions = {
  track_override: null,
  profile_override: null,
  emphasis_override: null,
  language_override: null,
  accept_low_fit: false,
  accept_incomplete_analysis: false,
  accepted_requirement_ids: [],
  acceptance_reason: null,
};

/* The form's own rule, and the only one it keeps: an empty submission is not a
   submission. It is not a copy of the server's "the submitted decisions change nothing"
   refusal, which also fires when a set value equals one already recorded - that answer
   stays the server's and is presented as it arrives. */
export const hasDecision = (decisions: ClassificationDecisions): boolean =>
  decisions.accept_low_fit ||
  decisions.accept_incomplete_analysis ||
  decisions.track_override != null ||
  decisions.profile_override != null ||
  decisions.emphasis_override != null ||
  decisions.language_override != null ||
  decisions.accepted_requirement_ids.length > 0;
