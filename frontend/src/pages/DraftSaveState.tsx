import type { AutosaveState } from "./useDraftAutosave";
import { LiveRegion } from "../ui/LiveRegion";

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

  return (
    <div className="flex flex-wrap items-center gap-2">
      <span className="text-support text-cv-text-muted">{label}</span>
      <LiveRegion>{label}</LiveRegion>
      {state.status === "failed" && state.message !== null ? (
        <span className="text-support text-cv-text-muted" dir="auto">
          {state.message}
        </span>
      ) : null}
    </div>
  );
};
