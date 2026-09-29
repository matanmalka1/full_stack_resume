import type { ReactNode } from "react";

import type { ApplicationDetail } from "@/api/contracts";
import { LtrText } from "@/ui/LtrText";
import { StatusBadge } from "@/ui/StatusBadge";
import { contentCheckLabels, contentCheckTones, documentStateLabels, documentStateTones } from "@/features/preparation";
import type { AutosaveState } from "../hooks/useDraftAutosave";
import type { EditableDocument } from "../model/drafts.types";
import { DraftSaveState } from "./DraftSaveState";

interface DraftHeaderCardProps {
  /* Screen-level controls that share the line, at its far end: the workspace switch. */
  actions?: ReactNode;
  detail: ApplicationDetail;
  /* Undefined while there is no content to edit, and then there is no save state either. */
  draft: EditableDocument | undefined;
  dirty: boolean;
  saveState: AutosaveState | null;
}

/* A.4 frame 3: which document is being edited, where it stands, and whether it is saved -
   the line the reader checks before navigating away.

   Both states are the projection's, never derived here: `document_state` restates the
   approval stamps against the current basis, and `content_check` says whether the stored
   report still describes this document. The short hash names the exact document; it is
   the token every command carries.

   A status line under the heading, not a card: framed at the column's full width it held
   a few small tags and read as an empty panel. */
export const DraftHeaderCard = ({ actions, detail, dirty, draft, saveState }: DraftHeaderCardProps) => (
  <div className="flex flex-wrap items-center justify-between gap-3">
    <div className="flex flex-wrap items-center gap-2">
      {draft === undefined ? null : (
        <LtrText
          className="rounded-pill border border-cv-border bg-cv-surface-muted px-2.5 py-1 text-support text-cv-text-muted"
          mono
          title={draft.document_hash}
        >
          {draft.document_hash.slice(0, 8)}
        </LtrText>
      )}
      <StatusBadge tone={documentStateTones[detail.document_state]}>
        {documentStateLabels[detail.document_state]}
      </StatusBadge>
      {detail.content_check === "none" ? null : (
        <StatusBadge tone={contentCheckTones[detail.content_check]}>
          {contentCheckLabels[detail.content_check]}
        </StatusBadge>
      )}
      {saveState === null ? null : <DraftSaveState dirty={dirty} state={saveState} />}
    </div>
    {actions}
  </div>
);
