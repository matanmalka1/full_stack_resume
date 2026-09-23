import type { ApplicationDetail } from "@/api/contracts";
import { hasWorkflowActionsContent, type WorkflowActionPlan } from "../../model/workflowActionPlan";
import { PreparationAlerts } from "./PreparationAlerts";
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
  detail,
  hasRecommendation,
  onQueued,
  operationLive,
  plan,
}: {
  detail: ApplicationDetail;
  /* Whether the projection names one specific action rather than merely permitting
     several. Decides which visual weight the action surface below takes. */
  hasRecommendation: boolean;
  onQueued: (operationId: string) => void;
  operationLive: boolean;
  plan: WorkflowActionPlan;
}) => {
  return (
    <>
      <PreparationAlerts detail={detail} />

      {/* The step's action, not a card around it. The action used to sit in an emphasized
          bordered box to mark it as recommended - but on a wizard step the action is the
          subject of the screen, not one card competing among others, and when it is a
          single "go to the editor" link the box was chrome around one button saying
          nothing the button did not. It stands on the page; its own primary styling is the
          emphasis.

          The named region moved inside `WorkflowActions`, which is the only place that can
          tell whether anything is actually left here to name: the commit bar portals out
          to the shell's action slot, so a labelled landmark drawn around it from here was
          empty on every step that offers a route and nothing else. */}
      {hasWorkflowActionsContent(plan) ? (
        <WorkflowActions
          detail={detail}
          hasRecommendation={hasRecommendation}
          onQueued={onQueued}
          operationLive={operationLive}
          plan={plan}
        />
      ) : null}
    </>
  );
};
