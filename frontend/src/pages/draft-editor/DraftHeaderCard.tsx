import { FileText } from "lucide-react";

import type { ApplicationDetail, WorkingDraft } from "../../api/contracts";
import { Card } from "../../ui/Card";
import { LtrText } from "../../ui/LtrText";
import { StatusBadge } from "../../ui/StatusBadge";
import { workingDraftStateLabels, workingDraftStateTones } from "../application/applicationLabels";
import { DraftSaveState } from "./DraftSaveState";
import type { useDraftAutosave } from "./useDraftAutosave";

interface DraftHeaderCardProps {
  autosave: ReturnType<typeof useDraftAutosave>;
  detail: ApplicationDetail;
  draft: WorkingDraft | undefined;
  workingDraftId: string | null;
}

/* A.4 frame 3: which Application this editor is open on, the version being edited, and
   whether it is saved - the one line the reader checks before navigating away. */
export const DraftHeaderCard = ({ autosave, detail, draft, workingDraftId }: DraftHeaderCardProps) => (
  <Card className="flex flex-wrap items-center justify-between gap-4 bg-cv-surface p-4 shadow-surface">
    <div className="flex min-w-0 items-center gap-3">
      <span className="grid size-10 shrink-0 place-items-center rounded-control bg-cv-accent-soft text-cv-accent">
        <FileText aria-hidden="true" className="size-5" />
      </span>
      <div className="min-w-0">
        <p className="truncate text-body font-bold text-cv-text" dir="auto">
          {detail.application.company}
        </p>
        <p className="truncate text-support text-cv-text-muted" dir="auto">
          {detail.application.target_role}
        </p>
      </div>
    </div>

    <div className="flex flex-wrap items-center justify-end gap-2">
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
      {workingDraftId === null ? null : <DraftSaveState state={autosave} />}
    </div>
  </Card>
);
