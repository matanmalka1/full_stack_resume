import type { ApplicationDetail } from "@/api/contracts";
import { StatusBadge } from "@/ui/StatusBadge";
import {
  draftStateIsImplied,
  preparationStateLabels,
  preparationStateTones,
  workingDraftStateLabels,
  workingDraftStateTones,
} from "../model/preparationLabels";

/* Where the CV stands, in the two words that say it: the preparation state the projection
   computed, and the working draft's own state where that is news rather than a restatement
   of the first.

   The caller supplies the row, because the badges belong to whatever layout is already
   laying one out. */
export const PreparationStatusBadges = ({ className, detail }: { className: string; detail: ApplicationDetail }) => (
  <div className={className}>
    <StatusBadge tone={preparationStateTones[detail.preparation_state]}>
      {preparationStateLabels[detail.preparation_state]}
    </StatusBadge>
    {draftStateIsImplied(detail) ? null : (
      <StatusBadge tone={workingDraftStateTones[detail.working_draft_state]}>
        {workingDraftStateLabels[detail.working_draft_state]}
      </StatusBadge>
    )}
  </div>
);
