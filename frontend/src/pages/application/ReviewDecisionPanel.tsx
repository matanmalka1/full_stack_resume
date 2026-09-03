import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";

import { applyAnalysisDecisions } from "../../api/analyses";
import { applicationDetailQueryKey } from "../../api/applications";
import type { ApplicationDetail, Reason } from "../../api/contracts";
import { ErrorCallout } from "../../app/ErrorCallout";
import { ActionBar } from "../../ui/ActionBar";
import { Button } from "../../ui/Button";
import {
  CLASSIFICATION_REASON,
  FIT_REASON,
  GAP_REASON,
  INCOMPLETE_ANALYSIS_REASON,
  REVIEW_REASONS_THIS_SCREEN_OWNS,
  ReviewDecisionForm,
  emptyDecisions,
  hasDecision,
} from "./ReviewDecisionForm";

/* Which review reasons this form resolves. Asked of the same table the standalone screen
   asks, so "this decision has a control" stays one fact in one place. */
export const resolvedByDecisionForm = (reason: Reason): boolean =>
  reason.allowed_resolution_actions.includes("apply_analysis_decisions") &&
  Object.hasOwn(REVIEW_REASONS_THIS_SCREEN_OWNS, reason.code);

/* The classification decision, on the Application screen and directly under the analysis
   it is about.

   It used to be a route of its own, which meant the decision was taken on one screen and
   the analysis being decided on was shown on another - so the standalone screen had to
   re-render the classification, the fit, and the gaps to give the reader anything to
   decide with. Both copies then had to be kept saying the same thing.

   Here the analysis is the panel above this one, so this holds only the controls, what
   they commit, and the refusal if the server declines. What is being decided is the
   `AnalysisPanel`; this is the deciding.

   It reports nothing about what happens next: `apply_analysis_decisions` is one commit
   and the refreshed projection is what says whether the reason closed. */
export const ReviewDecisionPanel = ({
  acceptableGapCount,
  acceptedRequirementIds,
  detail,
  onAcceptancesApplied,
}: {
  /* How many hard gaps of this analysis carry a Requirement to accept. The marks arrive
     from the gap list above, which is where they are taken; this panel only reports what
     is about to be sent and sends it. */
  acceptableGapCount: number;
  acceptedRequirementIds: readonly string[];
  detail: ApplicationDetail;
  onAcceptancesApplied: () => void;
}) => {
  const queryClient = useQueryClient();
  const [decisions, setDecisions] = useState(emptyDecisions);
  const applicationId = detail.application.id;

  /* The analysis being decided on is the one the projection calls active, which is also
     the one every review reason names in its entity references. */
  const analysisId = detail.active_analysis_id ?? null;
  /* The plan the acceptance is recorded against, and the plan the reader was shown. The
     server refuses an acceptance that does not name one, so without it the controls are
     withheld: with no active SelectionPlan the projection is asking for
     `FACT_SELECTION_UNRESOLVED`, which is a different reason with a different action. */
  const selectionPlanId = detail.active_selection_plan_id ?? null;
  const mine = detail.review_reasons.filter(resolvedByDecisionForm);
  const showClassification = mine.some((reason) => reason.code === CLASSIFICATION_REASON);
  const showFit = mine.some((reason) => reason.code === FIT_REASON);
  const showGapAcceptance = selectionPlanId !== null && mine.some((reason) => reason.code === GAP_REASON);
  const showIncompleteAnalysis = mine.some((reason) => reason.code === INCOMPLETE_ANALYSIS_REASON);

  /* The marks are the gap list's state, so they are merged in at the submission rather
     than copied into this panel's - one value, read where it is sent. */
  const submitted = { ...decisions, accepted_requirement_ids: showGapAcceptance ? [...acceptedRequirementIds] : [] };

  const apply = useMutation({
    mutationFn: async () => {
      if (analysisId === null) {
        throw new Error("apply_analysis_decisions was offered without an active analysis");
      }
      return applyAnalysisDecisions(analysisId, applicationId, submitted, selectionPlanId);
    },
    /* Nothing from the response body is seeded into the cache. `created_analysis` is read
       as what happened rather than assumed, and the refreshed projection is what reports
       the state that follows - which is this screen, so there is nowhere to navigate. */
    onSuccess: async () => {
      setDecisions(emptyDecisions);
      onAcceptancesApplied();
      await queryClient.invalidateQueries({ queryKey: applicationDetailQueryKey(applicationId) });
    },
  });

  if (mine.length === 0) {
    return null;
  }

  return (
    <section
      aria-labelledby="review-decision-heading"
      className="rounded-surface border border-cv-blocker/30 bg-cv-blocker/5 p-5"
    >
      <h2 className="text-body font-semibold text-cv-text" id="review-decision-heading">
        ההחלטה שנדרשת
      </h2>

      <div className="mt-4 flex flex-col gap-5">
        <ReviewDecisionForm
          decisions={decisions}
          disabled={apply.isPending}
          gapAcceptance={
            showGapAcceptance ? { acceptable: acceptableGapCount, marked: acceptedRequirementIds.length } : null
          }
          onChange={setDecisions}
          showClassification={showClassification}
          showFit={showFit}
          showIncompleteAnalysis={showIncompleteAnalysis}
        />

        {/* §13: what the commit does, and the two things the controls cannot say. What
            it writes depends on what was decided - a classification decision derives a
            new analysis, while a gap acceptance alone is recorded on a new SelectionPlan
            for the analysis on screen - so the sentence names both rather than promising
            the one that happens to be more common. */}
        <p className="text-support leading-6 text-cv-text-muted" dir="auto">
          כל ההחלטות נשלחות יחד בפעולה אחת. שינוי סיווג יוצר ניתוח חדש ובלתי משתנה יחד עם תוכנית הבחירה ההתחלתית שלו,
          וקבלת פער נרשמת בתוכנית בחירה חדשה עבור אותו ניתוח. הניתוח והתוכנית שעליהם הוחלט נשמרים בדיוק כפי שהם. החלטות
          מצטברות: השארת שדה ריק שומרת על החלטה קודמת ואינה מבטלת אותה.
        </p>

        {apply.error === null ? null : (
          <ErrorCallout
            error={apply.error}
            fallbackDetail="הפנייה לשרת נכשלה. שום החלטה לא נרשמה ואפשר לנסות שוב."
            fallbackTitle="ההחלטות לא הוחלו"
          />
        )}

        <ActionBar
          align="start"
          primary={
            <Button
              disabled={!hasDecision(submitted) || analysisId === null}
              onClick={() => apply.mutate()}
              pending={apply.isPending}
              pendingLabel="מחיל את ההחלטות…"
            >
              החלת כל ההחלטות
            </Button>
          }
        />
      </div>
    </section>
  );
};
