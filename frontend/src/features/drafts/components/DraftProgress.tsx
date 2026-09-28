import { ArrowLeft, OctagonAlert } from "lucide-react";

import type { ApplicationDetail } from "@/api/contracts";
import { formatDateTime } from "@/utils/formatDateTime";
import type { AutosaveState } from "../hooks/useDraftAutosave";
import { type ContentSummary, type DraftStepId, draftSteps } from "../model/draftOverview";
import type { EditableDocument } from "../model/drafts.types";
import { DraftSaveState } from "./DraftSaveState";

interface DraftProgressProps {
  content: ContentSummary;
  detail: ApplicationDetail;
  dirty: boolean;
  draft: EditableDocument;
  saveState: AutosaveState;
}

/* What the part of the draft step waiting on the reader asks of them. */
const guidance: Record<DraftStepId, string> = {
  review: "יש לטפל בשורות שאין מאחוריהן עובדה מאושרת. הן מסומנות למטה, והאישור חסום עד שיטופלו.",
  check: "התוכן מבוסס. אפשר לעבור על הטיוטה, ואז הכפתור בתחתית בודק את הקובץ ופותח את האישור.",
  approve: "הבדיקה עברה. האישור מפיק HTML ו־PDF סופיים; עריכה אחריו מחזירה את המסמך לטיוטה.",
};

/* One line under the heading: what to do now, and whether the work is saved.

   Not a stepper. The workflow spine above the heading already draws where this step sits
   in the flow; a second row of steps inside it repeated that shape for the step's own
   parts. What the reader needs here is the next thing to do, read from the projection
   (`document_state`, `content_check`, `review_reasons`) and the outline's claim types.
   Nothing here decides whether a command is available. */
export const DraftProgress = ({ content, detail, dirty, draft, saveState }: DraftProgressProps) => {
  const focus = draftSteps(detail, content).find((step) => step.status === "blocked" || step.status === "current");
  const blocked = focus?.status === "blocked";

  return (
    <div className="flex flex-wrap items-center justify-between gap-x-6 gap-y-2 border-b border-cv-hairline pb-4">
      {focus === undefined ? (
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
            {guidance[focus.id]}
          </span>
        </p>
      )}
      <div className="flex flex-wrap items-center gap-x-3 gap-y-1 text-caption text-cv-text-muted">
        <DraftSaveState dirty={dirty} state={saveState} />
        <span>עודכנה {formatDateTime(draft.updated_at, "short")}</span>
      </div>
    </div>
  );
};
