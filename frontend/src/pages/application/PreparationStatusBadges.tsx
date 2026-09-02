import type { ApplicationDetail } from "../../api/contracts";
import { preparationStateIsImpliedByStage } from "../../app/WorkflowLandmark";
import { StatusBadge } from "../../ui/StatusBadge";
import {
  draftStateIsImplied,
  preparationStateLabels,
  preparationStateTones,
  workingDraftStateLabels,
  workingDraftStateTones,
} from "./applicationLabels";

export const PreparationStatusBadges = ({
  className,
  detail,
  hideStageImpliedStatus = false,
}: {
  className: string;
  detail: ApplicationDetail;
  hideStageImpliedStatus?: boolean;
}) => (
  <div className={className}>
    {hideStageImpliedStatus && preparationStateIsImpliedByStage(detail.preparation_state) ? null : (
      <StatusBadge tone={preparationStateTones[detail.preparation_state]}>
        {preparationStateLabels[detail.preparation_state]}
      </StatusBadge>
    )}
    {draftStateIsImplied(detail) ? null : (
      <StatusBadge tone={workingDraftStateTones[detail.working_draft_state]}>
        {workingDraftStateLabels[detail.working_draft_state]}
      </StatusBadge>
    )}
  </div>
);
