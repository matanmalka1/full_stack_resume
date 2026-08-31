import { Check, CloudAlert, CloudUpload } from "lucide-react";

import { LiveRegion } from "../../ui/LiveRegion";
import { cx } from "../../ui/cx";
import type { AutosaveState } from "./useDraftAutosave";

const labels: Record<AutosaveState["status"], string> = {
  idle: "",
  saving: "שומר…",
  saved: "נשמר",
  failed: "השמירה נכשלה",
  conflict: "השמירה נעצרה בגלל שינוי מקביל",
};

/* A.4: autosave shows its state and announces it, and never moves focus while doing so.
   The live region is the announcement; the visible text beside it is for everyone else. */
export const DraftSaveState = ({ state }: { state: AutosaveState }) => {
  const label = labels[state.status];
  const Icon =
    state.status === "saving"
      ? CloudUpload
      : state.status === "failed" || state.status === "conflict"
        ? CloudAlert
        : Check;

  return (
    <div className="flex flex-wrap items-center gap-2">
      {label === "" ? null : (
        <span
          className={cx(
            "inline-flex items-center gap-1.5 rounded-pill px-2.5 py-1 text-support font-semibold",
            state.status === "failed" || state.status === "conflict"
              ? "bg-cv-blocker-soft text-cv-blocker"
              : state.status === "saved"
                ? "bg-cv-success-soft text-cv-success"
                : "bg-cv-accent-soft text-cv-accent",
          )}
        >
          <Icon aria-hidden="true" className="size-3.5" />
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
