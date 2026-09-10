import type { Classification } from "@/api/analyses";
import type { ApplicationDetail } from "@/api/contracts";
import type { WorkflowActionPlan } from "../../model/workflowActionPlan";
import { AnalysisPanel } from "./AnalysisPanel";
import { ReanalyzeCard } from "./ReanalyzeCard";

/* The diagnostics tab: the full analysis, and re-running it beside the record it would
   replace. One region for `PreparationView` to hand an Application to, rather than the
   two siblings it used to compose inline. */
export const AnalysisStage = ({
  classification,
  detail,
  onQueued,
  plan,
  showGaps,
}: {
  classification: Classification;
  detail: ApplicationDetail;
  onQueued: (operationId: string) => void;
  plan: WorkflowActionPlan;
  showGaps: boolean;
}) => (
  <AnalysisPanel
    classification={classification}
    detail={detail}
    /* Asked here rather than left to the card's own early return: the panel gives its
       footer a band of its own, and a card that renders nothing would still have cost a
       divider and a band of padding at the foot of the panel. */
    footer={
      plan.analyze?.reanalysis === true ? <ReanalyzeCard detail={detail} onQueued={onQueued} plan={plan} /> : undefined
    }
    showGaps={showGaps}
  />
);
