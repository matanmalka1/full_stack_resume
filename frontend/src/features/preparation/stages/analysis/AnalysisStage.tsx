import type { Classification } from "@/api/analyses";
import type { ApplicationDetail } from "@/api/contracts";
import type { WorkflowActionPlan } from "../../model/workflowActionPlan";
import { AnalysisPanel } from "./AnalysisPanel";
import { ReanalyzeCard } from "./ReanalyzeCard";

export const AnalysisStage = ({
  classification,
  detail,
  onQueued,
  operationLive,
  plan,
}: {
  classification: Classification;
  detail: ApplicationDetail;
  onQueued: (operationId: string) => void;
  operationLive: boolean;
  plan: WorkflowActionPlan;
}) => (
  <AnalysisPanel
    classification={classification}
    detail={detail}
    footer={
      plan.analyze?.reanalysis === true ? (
        <ReanalyzeCard detail={detail} onQueued={onQueued} operationLive={operationLive} />
      ) : undefined
    }
  />
);
