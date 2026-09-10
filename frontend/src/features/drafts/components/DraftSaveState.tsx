import { Check, CloudAlert, CloudUpload } from "lucide-react";

import { LiveRegion } from "@/ui/LiveRegion";
import { cx } from "@/ui/cx";
import type { AutosaveState } from "../hooks/useDraftAutosave";

const labels: Record<AutosaveState["status"], string> = {
  idle: "",
  saving: "שומר…",
  saved: "נשמר",
  failed: "השמירה נכשלה",
  conflict: "השמירה נעצרה בגלל שינוי מקביל",
};

const UNSAVED_LABEL = "שינויים לא נשמרו";

interface DraftSaveStateProps {
  /* Text the server has not accepted yet. Between the keystroke and the debounce the
     status is still `idle`, and that gap used to show nothing at all - the one moment the
     reader most needs to know not to walk away. */
  dirty: boolean;
  state: AutosaveState;
}

/* A.4: autosave shows its state and announces it, and never moves focus while doing so.
   The live region is the announcement; the visible text beside it is for everyone else. */
export const DraftSaveState = ({ dirty, state }: DraftSaveStateProps) => {
  const label = state.status === "idle" && dirty ? UNSAVED_LABEL : labels[state.status];
  const failed = state.status === "failed" || state.status === "conflict";
  const Icon = failed ? CloudAlert : state.status === "saved" ? Check : CloudUpload;

  return (
    <div className="flex flex-wrap items-center gap-2">
      {label === "" ? null : (
        <span
          className={cx(
            "inline-flex items-center gap-1.5 rounded-pill px-2.5 py-1 text-support font-semibold",
            failed
              ? "bg-cv-blocker-soft text-cv-blocker"
              : state.status === "saved"
                ? "bg-cv-success-soft text-cv-success"
                : label === UNSAVED_LABEL
                  ? "bg-cv-warning-soft text-cv-warning"
                  : "bg-cv-accent-soft text-cv-accent",
          )}
        >
          <Icon aria-hidden="true" className="size-icon-sm" />
          {label}
        </span>
      )}
      <LiveRegion>{label}</LiveRegion>
      {state.status === "failed" && state.message !== null ? (
        <span className="text-support text-cv-text-muted" dir="auto">
          {state.message}
        </span>
      ) : null}
    </div>
  );
};
