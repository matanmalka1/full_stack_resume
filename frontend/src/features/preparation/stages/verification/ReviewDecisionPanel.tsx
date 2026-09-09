import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";

import type { Classification } from "@/api/analyses";
import { applyAnalysisDecisions } from "@/api/analyses";
import { invalidateApplicationViews } from "@/api/applications";
import type { ApplicationDetail } from "@/api/contracts";
import { ErrorCallout } from "@/ui/ErrorCallout";
import { Button } from "@/ui/Button";
import { Disclosure } from "@/ui/Disclosure";
import { surfaceClasses } from "@/ui/surface";
import { emptyDecisions, hasDecision, openDecisions, resolvedByReviewDecision } from "../../model/reviewDecisions";
import { type ChecklistEntry, CommitBar, CommitChecklist } from "../../components/CommitBar";
import { GapsSection } from "../analysis/GapsSection";
import { ReviewDecisionForm } from "./ReviewDecisionForm";

/* The classification decision, on the Application screen and directly under the analysis
   it is about.

   It used to be a route of its own, which meant the decision was taken on one screen and
   the analysis being decided on was shown on another - so the standalone screen had to
   re-render the classification, the fit, and the gaps to give the reader anything to
   decide with. Both copies then had to be kept saying the same thing.

   Here the analysis is the panel above this one, so this holds only the controls, what
   they commit, and the refusal if the server declines. What is being decided is the
   `AnalysisPanel`; this is the deciding.

   A hard-gap acceptance is taken here too, not in a card of its own beside this one: the
   mark and the rest of the decision are one submission, and a reader marking a gap is
   already inside the "what do I have to decide" surface rather than arriving at it from
   somewhere else on the tab. Its own state stays local for the same reason the rest of
   the form's does - cleared on a successful commit, in the same beat the form clears.

   It reports nothing about what happens next: `apply_analysis_decisions` is one commit
   and the refreshed projection is what says whether the reason closed. */
export const ReviewDecisionPanel = ({
  classification,
  detail,
}: {
  /* Read both to name the values the override selects would replace and to render the
     gap list a hard-gap acceptance is taken against. */
  classification: Classification | null;
  detail: ApplicationDetail;
}) => {
  const queryClient = useQueryClient();
  const [decisions, setDecisions] = useState(emptyDecisions);
  const [acceptedRequirementIds, setAcceptedRequirementIds] = useState<string[]>([]);
  const toggleAcceptance = (requirementId: string) =>
    setAcceptedRequirementIds((current) =>
      current.includes(requirementId) ? current.filter((id) => id !== requirementId) : [...current, requirementId],
    );
  const applicationId = detail.application.id;

  /* The analysis being decided on is the one the projection calls active, which is also
     the one every review reason names in its entity references. */
  const analysisId = detail.active_analysis_id ?? null;
  /* The plan the acceptance is recorded against, and the plan the reader was shown. The
     server refuses an acceptance that does not name one, so without it the controls are
     withheld: with no active SelectionPlan the projection is asking for
     `FACT_SELECTION_UNRESOLVED`, which is a different reason with a different action. */
  const selectionPlanId = detail.active_selection_plan_id ?? null;
  const mine = detail.review_reasons.filter(resolvedByReviewDecision);
  const open = openDecisions(detail);
  const showClassification = open.classification;
  const showFit = open.fit;
  const showGapAcceptance = open.gaps;
  const showIncompleteAnalysis = open.incompleteAnalysis;
  /* Only a hard gap that names a Requirement can be accepted - the id is the whole of
     what an acceptance records. `GapsSection` applies the same rule per gap; this is the
     count the checklist and the form's helper sentence read. */
  const acceptableGapCount =
    classification === null
      ? 0
      : classification.gaps.filter((gap) => gap.severity === "hard" && gap.requirementId !== null).length;

  /* The marks are the gap list's state, so they are merged in at the submission rather
     than copied into this panel's - one value, read where it is sent. */
  const submitted = { ...decisions, accepted_requirement_ids: showGapAcceptance ? [...acceptedRequirementIds] : [] };

  const classificationReady =
    !showClassification || decisions.track_override !== null || decisions.profile_override !== null;
  const incompleteAnalysisReady = !showIncompleteAnalysis || decisions.accept_incomplete_analysis;
  const fitReady = !showFit || decisions.accept_low_fit;
  const gapsReady = !showGapAcceptance || acceptedRequirementIds.length > 0;
  const decisionReady =
    analysisId !== null &&
    hasDecision(submitted) &&
    classificationReady &&
    incompleteAnalysisReady &&
    fitReady &&
    gapsReady;

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
      setAcceptedRequirementIds([]);
      await invalidateApplicationViews(queryClient, applicationId);
    },
  });

  if (mine.length === 0) {
    return null;
  }

  /* The live state of every decision the projection is asking for, in the bar that
     commits them. What stood here was a single sentence saying something was missing,
     under the button and out of sight on a long form. */
  const checklist: ChecklistEntry[] = [
    ...(showClassification ? [{ done: classificationReady, label: "בחירת מסלול או פרופיל" }] : []),
    ...(showIncompleteAnalysis ? [{ done: incompleteAnalysisReady, label: "אישור שהדרישות לא נקראו" }] : []),
    ...(showFit ? [{ done: fitReady, label: "אישור ההתאמה הנמוכה" }] : []),
    ...(showGapAcceptance ? [{ done: gapsReady, label: "סימון פער חוסם לקבלה" }] : []),
  ];

  return (
    <>
      <section aria-labelledby="review-decision-heading" className={surfaceClasses("bg-cv-surface p-5 shadow-surface")}>
        {/* How many decisions are open is the checklist's to count and the sub-tab
            badge's to announce; the heading names the surface and stops, so the number
            is not restated a place it can fall out of step with them. */}
        <h2 className="text-body font-semibold text-cv-text" id="review-decision-heading">
          החלטות נדרשות כדי להמשיך
        </h2>

        <div className="mt-4 flex flex-col gap-5">
          {/* A hard-gap decision is taken on the exact gap it is about, so the gap list
              stands inside the same card as the rest of the decision rather than beside
              it as a card of its own. */}
          {showGapAcceptance && classification !== null ? (
            <GapsSection
              acceptance={{ disabled: apply.isPending, onToggle: toggleAcceptance, selected: acceptedRequirementIds }}
              gaps={classification.gaps}
            />
          ) : null}

          {/* The border only appears once there is a gap list above to separate this
              form from - two decisions read as two, one decision as one. */}
          <div className={showGapAcceptance && classification !== null ? "border-t border-cv-border pt-5" : undefined}>
            <ReviewDecisionForm
              classification={classification}
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
          </div>

          {/* §13: what the commit does, and the two things the controls cannot say. What
              it writes depends on what was decided - a classification decision derives a
              new analysis, while a gap acceptance alone is recorded on a new SelectionPlan
              for the analysis on screen - so the sentence names both rather than promising
              the one that happens to be more common. */}
          <Disclosure summary="מה יישמר לאחר האישור?">
            <p dir="auto">
              כל ההחלטות נשלחות יחד. שינוי סיווג יוצר ניתוח ותוכנית בחירה חדשים; קבלת פער נרשמת בתוכנית בחירה חדשה.
              הרשומות הקודמות נשמרות, ושדה שלא שונה אינו מבטל החלטה קודמת.
            </p>
          </Disclosure>

          {apply.error === null ? null : (
            <ErrorCallout
              error={apply.error}
              fallbackDetail="הפנייה לשרת נכשלה. שום החלטה לא נרשמה ואפשר לנסות שוב."
              fallbackTitle="ההחלטות לא הוחלו"
            />
          )}
        </div>
      </section>

      <CommitBar
        primary={
          <Button
            disabled={!decisionReady}
            onClick={() => apply.mutate()}
            pending={apply.isPending}
            pendingLabel="שומר את ההחלטות…"
          >
            שמירת ההחלטות
          </Button>
        }
      >
        <CommitChecklist entries={checklist} label="ההחלטות הנדרשות" />
        {decisionReady ? null : (
          <p className="text-support font-medium text-cv-blocker">
            יש להשלים את כל ההחלטות שמופיעות בכרטיס לפני שאפשר לשמור.
          </p>
        )}
      </CommitBar>
    </>
  );
};
