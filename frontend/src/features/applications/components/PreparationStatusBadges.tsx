import type { ApplicationDetail } from "@/api/contracts";
import { preparationStateIsImpliedByStage } from "@/app/WorkflowLandmark";
import { StatusBadge } from "@/ui/StatusBadge";
import {
  draftStateIsImplied,
  preparationStateLabels,
  preparationStateTones,
  workingDraftStateLabels,
  workingDraftStateTones,
} from "@/features/applications/model/applicationLabels";

export const PreparationStatusBadges = ({
  /* `contents` by default: the badges become direct children of whatever row the caller
     already lays out, so a call site that has its own flex row does not have to restate
     its gap here. A caller that owns no such row passes one. */
  className = "contents",
  detail,
  hideStageImpliedStatus = false,
}: {
  className?: string;
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
