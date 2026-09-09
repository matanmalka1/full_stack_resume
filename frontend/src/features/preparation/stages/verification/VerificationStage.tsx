import type { Classification } from "@/api/analyses";
import type { ApplicationDetail } from "@/api/contracts";
import { openDecisionCount, openDecisions } from "../../model/reviewDecisions";
import { hasWorkflowActionsContent, type WorkflowActionPlan } from "../../model/workflowActionPlan";
import { PreparationAlerts } from "./PreparationAlerts";
import { ReviewDecisionPanel } from "./ReviewDecisionPanel";
import { WorkflowActions } from "./WorkflowActions";

/* The "what do I need to decide, and what do I do next" workspace: everything the
   Application screen's decisions tab shows. It composes rather than the screen itself,
   so `PreparationView` hands over one Application and reads back one region instead of
   assembling four siblings inline.

   Three surfaces, never merged into one: alerts are read-only, the decision panel is a
   form with its own commit, and the action bar is a row of commands. Folding them into a
   single card would blur a reader's read/write/act boundaries; kept apart with plain
   spacing between them - no extra chrome - they still read as one continuous next step
   rather than as unrelated regions. */
export const VerificationStage = ({
  classification,
  detail,
  hasRecommendation,
  onQueued,
  plan,
}: {
  classification: Classification | null;
  detail: ApplicationDetail;
  /* Whether the projection is naming one specific action - `recommended_action`, or a
     review decision this tab holds the control for - rather than merely permitting
     several. Decides which visual weight the action surface below takes. */
  hasRecommendation: boolean;
  onQueued: (operationId: string) => void;
  plan: WorkflowActionPlan;
}) => {
  /* One commit at a time. The decision panel owns a viewport-sticky commit bar; drawing
     the action card below it put two "do this next" surfaces on the tab and let the sticky
     bar float over the second. While a decision this screen owns is open it is the next
     step - and it gates the actions the card would offer anyway - so the card waits for the
     refreshed projection after the commit rather than sitting behind the bar that resolves
     what blocks it. */
  const decisionOpen = openDecisionCount(openDecisions(detail)) > 0;

  return (
    <>
      <PreparationAlerts detail={detail} />

      <ReviewDecisionPanel classification={classification} detail={detail} />

      {!decisionOpen && hasWorkflowActionsContent(plan) ? (
        /* The step's action, not a card around it. The action used to sit in an emphasized
           bordered box to mark it as recommended - but on a wizard step the action is the
           subject of the screen, not one card competing among others, and when it is a
           single "go to the editor" link the box was chrome around one button saying
           nothing the button did not. It stands on the page; its own primary styling is the
           emphasis. */
        <section aria-label={hasRecommendation ? "הפעולה המומלצת" : "פעולות זמינות"}>
          <WorkflowActions detail={detail} onQueued={onQueued} plan={plan} />
        </section>
      ) : null}
    </>
  );
};
