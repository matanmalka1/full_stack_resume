import { ArrowLeft, OctagonAlert } from "lucide-react";
import type { ReactNode } from "react";

import type { ApplicationDetail } from "@/api/contracts";
import { formatDateTime } from "@/utils/formatDateTime";
import type { AutosaveState } from "../hooks/useDraftAutosave";
import { type ContentSummary, type DraftStepId, draftSteps } from "../model/draftOverview";
import type { EditableDocument } from "../model/drafts.types";
import { DraftSaveState } from "./DraftSaveState";

interface DraftProgressProps {
  actions?: ReactNode;
  content: ContentSummary;
  detail: ApplicationDetail;
  dirty: boolean;
  draft: EditableDocument;
  saveState: AutosaveState;
}

/* What the part of the draft step waiting on the reader asks of them - said here only
   where it adds to the pinned bar. The bar already says what to do next for a document
   that can go on to its check or its approval, and this line repeating it put the same
   instruction at the top and the bottom of the screen; on a phone the two together took
   half of the first screen. A blocked document is the exception: the bar says only that
   something blocks, and this line says where. */
const guidance: Partial<Record<DraftStepId, string>> = {
  review: "יש לטפל בשורות שאין מאחוריהן עובדה מאושרת. הן מסומנות למטה, והאישור חסום עד שיטופלו.",
};

/* One line under the heading: what to do now, and whether the work is saved.

   Not a stepper. The workflow spine above the heading already draws where this step sits
   in the flow; a second row of steps inside it repeated that shape for the step's own
   parts. What the reader needs here is the next thing to do, read from the projection
   (`preparation_state`, `content_check`, `review_reasons`) and the outline's claim types.
   Nothing here decides whether a command is available. */
export const DraftProgress = ({ actions, content, detail, dirty, draft, saveState }: DraftProgressProps) => {
  const focus = draftSteps(detail, content).find((step) => step.status === "blocked" || step.status === "current");
  const blocked = focus?.status === "blocked";
  const line = focus === undefined ? undefined : guidance[focus.id];

  return (
    <div className="flex flex-wrap items-center justify-between gap-x-6 gap-y-2 border-b border-cv-hairline pb-4">
      {line === undefined ? (
        <span />
      ) : (
        <p className="flex min-w-0 items-start gap-2 text-support leading-6 text-cv-text">
          {blocked ? (
            <OctagonAlert aria-hidden="true" className="mt-1 size-icon-md shrink-0 text-cv-blocker" />
          ) : (
            <ArrowLeft aria-hidden="true" className="mt-1 size-icon-md shrink-0 text-cv-accent" />
          )}
          <span>
            <span className="font-semibold">מה עכשיו: </span>
            {line}
          </span>
        </p>
      )}
      <div className="flex flex-wrap items-center gap-x-3 gap-y-1 text-caption text-cv-text-muted">
        <DraftSaveState dirty={dirty} state={saveState} />
        <span>עודכנה {formatDateTime(draft.updated_at, "short")}</span>
        {actions}
      </div>
    </div>
  );
};
