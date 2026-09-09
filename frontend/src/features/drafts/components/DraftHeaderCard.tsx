import type { ApplicationDetail, WorkingDraft } from "@/api/contracts";
import { Card } from "@/ui/Card";
import { LtrText } from "@/ui/LtrText";
import { StatusBadge } from "@/ui/StatusBadge";
import { workingDraftStateLabels, workingDraftStateTones } from "@/features/preparation";
import type { AutosaveState } from "../hooks/useDraftAutosave";
import { DraftSaveState } from "./DraftSaveState";

interface DraftHeaderCardProps {
  detail: ApplicationDetail;
  /* Undefined while there is no draft to edit, and then there is no save state either. */
  draft: WorkingDraft | undefined;
  dirty: boolean;
  saveState: AutosaveState | null;
}

/* A.4 frame 3: which version is being edited and whether it is saved - the line the
   reader checks before navigating away.

   Which Application it belongs to is not repeated here. The card used to open with the
   company and the target role, two lines under a breadcrumb trail that had just named the
   same pair; the identity is the trail's to state, and what only this card can say is the
   version, its hash, the draft's state and whether the last edit reached the server. */
export const DraftHeaderCard = ({ detail, dirty, draft, saveState }: DraftHeaderCardProps) => (
  <Card className="flex flex-wrap items-center justify-between gap-4 bg-cv-surface p-4 shadow-surface">
    <div className="flex flex-wrap items-center gap-2">
      {draft === undefined ? null : (
        <LtrText
          className="rounded-pill border border-cv-border bg-cv-surface-muted px-2.5 py-1 text-support text-cv-text-muted"
          mono
          title={draft.content_hash}
        >
          v{draft.edit_version} · {draft.content_hash.slice(0, 10)}
        </LtrText>
      )}
      <StatusBadge tone={workingDraftStateTones[detail.working_draft_state]}>
        {workingDraftStateLabels[detail.working_draft_state]}
      </StatusBadge>
      {saveState === null ? null : <DraftSaveState dirty={dirty} state={saveState} />}
    </div>
  </Card>
);
