import { Check, CloudAlert, CloudUpload } from "lucide-react";
import type { ReactNode } from "react";

import { LiveRegion } from "@/ui/LiveRegion";
import { cx } from "@/ui/cx";
import type { AutosaveState } from "../hooks/useDraftAutosave";

const SAVED_LABEL = "השינויים נשמרו";

const labels: Record<AutosaveState["status"], string> = {
  idle: SAVED_LABEL,
  saving: "שומר…",
  saved: SAVED_LABEL,
  failed: "השמירה נכשלה",
  conflict: "השמירה נעצרה בגלל שינוי מקביל",
};

const UNSAVED_LABEL = "שינויים לא נשמרו";

interface DraftSaveStateProps {
  /* Text the server has not accepted yet. Between the keystroke and the debounce the
     status is still `idle`, and that gap used to read as saved - the one moment the
     reader most needs to know not to walk away. */
  dirty: boolean;
  state: AutosaveState;
  /* Drawn at the block's far end: the undo and redo of the edits it reports on. */
  trailing?: ReactNode;
}

/* A.4: autosave shows its state and announces it, and never moves focus while doing so.
   The design gives it a quiet block of its own under the fit; a failure is the same block
   in the strong edge, with the server's sentence under it.

   The live region speaks only a change: a document opened with nothing to save is
   simply shown as saved, not announced. */
export const DraftSaveState = ({ dirty, state, trailing }: DraftSaveStateProps) => {
  const label = state.status === "idle" && dirty ? UNSAVED_LABEL : labels[state.status];
  const failed = state.status === "failed" || state.status === "conflict";
  const Icon = failed ? CloudAlert : label === SAVED_LABEL ? Check : CloudUpload;

  return (
    <div
      className={cx(
        "flex flex-col gap-1 rounded-control-lg bg-cv-surface-muted px-3.5 py-3 text-support text-cv-text",
        failed && "border border-cv-border-strong",
      )}
    >
      <div className="flex items-center gap-2">
        <Icon aria-hidden="true" className="size-icon-md shrink-0" />
        <span className={cx("min-w-0 flex-1", failed && "font-bold")}>{label}</span>
        {trailing}
      </div>
      <LiveRegion>{state.status === "idle" && !dirty ? "" : label}</LiveRegion>
      {state.status === "failed" && state.message !== null ? (
        <span className="text-caption text-cv-text-muted" dir="auto">
          {state.message}
        </span>
      ) : null}
    </div>
  );
};
