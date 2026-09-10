import { classificationFromAnalysis, lowFitAcceptedFromAnalysis } from "@/api/analyses";
import type { ApplicationDetail } from "@/api/contracts";
import { Disclosure } from "@/ui/Disclosure";
import { openDecisionCount, openDecisions, resolvedByReviewDecision } from "../model/reviewDecisions";
import { workflowActionPlan } from "../model/workflowActionPlan";
import { AnalysisStage } from "../stages/analysis/AnalysisStage";
import { SelectionPlanPanel } from "../stages/content/SelectionPlanPanel";
import { VerificationStage } from "../stages/verification/VerificationStage";
import { AnalysisStatusBanner } from "./AnalysisStatusBanner";
import { AutomaticDraftNotice } from "./AutomaticDraftNotice";

/* Preparing one Application's CV, as a single step of the workflow wizard rather than a
   hub of tabs.

   The screen used to be a record you browsed: a tab bar over decisions, facts and the
   diagnosis, a second bar over the posting and the files, a two-axis state panel, and a
   recruitment column - several readings of the same projection side by side at the same
   weight. None of that is the task. The task is the one thing the workflow is waiting on,
   and it is stated once: the verdict, then the single action panel that answers it.

   What supported the old tabs is still reachable, but as reference a press away rather
   than as panels competing for the same space. The facts the CV will carry, the full
   diagnosis, and the posting text sit below the action in collapsed disclosures - opened
   when a reader wants to adjust or check something, closed by default so the screen shows
   the step and its action and nothing beside them. */
export const PreparationView = ({
  detail,
  onQueued,
}: {
  detail: ApplicationDetail;
  onQueued: (operationId: string) => void;
}) => {
  const classification = classificationFromAnalysis(detail);
  /* The active analysis as this screen reads it: an analysis of a superseded job snapshot
     is on record but is not what the workflow stands on, so it is reported as absent. */
  const supersededAnalysis = classification === null && detail.latest_analysis != null;

  const plan = workflowActionPlan(detail);
  const open = openDecisions(detail);
  const decisionCount = openDecisionCount(open);
  const lowFitAccepted = lowFitAcceptedFromAnalysis(detail);
  const hasRecommendation = detail.review_reasons.some(resolvedByReviewDecision) || detail.recommended_action != null;
  const selectionPlanAction = plan.createSelectionPlan;

  /* Open decisions stay visible until answered. A recorded low-fit acceptance remains as
     useful history, but with copy that names it as closed. The absence of a draft is not
     itself a reason to keep an otherwise completed verdict on screen. */
  const incompleteAnalysisAccepted =
    classification?.fit === "unknown" && !open.incompleteAnalysis && detail.preparation_state !== "needs_analysis";
  const showBanner =
    supersededAnalysis || classification === null || decisionCount > 0 || lowFitAccepted || incompleteAnalysisAccepted;

  return (
    <div className="flex flex-col gap-4">
      <AutomaticDraftNotice detail={detail} />

      {/* The verdict the step is about, stated once and first - while it is still the
          step's verdict. */}
      {showBanner ? (
        <AnalysisStatusBanner
          classification={classification}
          hasOpenDecisions={decisionCount > 0}
          incompleteAnalysisAccepted={incompleteAnalysisAccepted}
          lowFitAccepted={lowFitAccepted}
          lowFitDecisionOpen={open.fit}
          supersededAnalysis={supersededAnalysis}
        />
      ) : null}

      {/* The one thing to do now: run the analysis, resolve the open decisions, or generate
          the draft and move to the editor. Everything else on the screen is below it and
          closed. */}
      <VerificationStage
        classification={classification}
        detail={detail}
        hasRecommendation={hasRecommendation}
        onQueued={onQueued}
        plan={plan}
      />

      {/* Adjusting which facts the CV carries is a refinement of the generate step, not a
          parallel destination - offered where it is done, folded away until wanted. */}
      {selectionPlanAction === null ? null : (
        <Disclosure summary="התאמת העובדות שייכנסו לקורות החיים">
          <div className="pt-2">
            <SelectionPlanPanel action={selectionPlanAction} detail={detail} onQueued={onQueued} />
          </div>
        </Disclosure>
      )}

      {/* The reasoning behind the verdict, for a reader who wants to check it before acting.
          It decides nothing; the acceptance controls it once held are in the step above. */}
      {classification === null ? null : (
        <Disclosure summary="פרטי הניתוח והאבחון">
          <div className="pt-2">
            <AnalysisStage
              classification={classification}
              detail={detail}
              onQueued={onQueued}
              plan={plan}
              showGaps={!open.gaps}
            />
          </div>
        </Disclosure>
      )}
    </div>
  );
};
