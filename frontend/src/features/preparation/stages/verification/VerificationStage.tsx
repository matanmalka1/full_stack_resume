import type { Classification } from "@/api/analyses";
import type { ApplicationDetail } from "@/api/contracts";
import { surfaceClasses } from "@/ui/surface";
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
}) => (
  <>
    <PreparationAlerts detail={detail} />

    <ReviewDecisionPanel classification={classification} detail={detail} />

    {hasWorkflowActionsContent(plan) ? (
      <section
        aria-label={hasRecommendation ? "הפעולה המומלצת" : "פעולות זמינות"}
        className={
          hasRecommendation
            ? "rounded-surface border-2 border-cv-accent/25 bg-cv-accent-soft/40 p-5 shadow-surface"
            : surfaceClasses("bg-cv-surface p-5")
        }
      >
        <WorkflowActions detail={detail} onQueued={onQueued} plan={plan} />
      </section>
    ) : null}
  </>
);
