import type { ReactNode } from "react";

import { cx } from "@/ui/cx";
import { ViewSwitch } from "@/ui/ViewSwitch";

/* What the screen is for at this moment. `read` is the primary desktop workspace: clean
   inline editing beside the rendered document. `document` is a focused preview for narrow
   screens or for a final full-width read. */
export type DraftWorkspaceMode = "read" | "document";

interface DraftWorkspaceProps {
  /* The claim column: the draft as rows, each with its own editing controls. */
  editor: ReactNode;
  /* Chosen by `DraftWorkspaceSwitch`, which the page places; switching to `document`
     settles the autosave buffer first, which is the page's business rather than the
     layout's. */
  mode: DraftWorkspaceMode;
  preview: ReactNode;
}

/* The mode switch. It sits in the status line under the heading rather than on a row of
   its own above the workspace: alone there it was a band of empty width with one control
   at its far end. */
export const DraftWorkspaceSwitch = ({
  mode,
  onModeChange,
}: {
  mode: DraftWorkspaceMode;
  onModeChange: (mode: DraftWorkspaceMode) => void;
}) => (
  <ViewSwitch
    label="בחירת תצוגת סביבת העבודה"
    onChange={onModeChange}
    options={[
      { label: "עריכה ותצוגה", value: "read" },
      { label: "תצוגה מלאה", value: "document" },
    ]}
    value={mode}
  />
);

/* A.4's responsive fallback. Both panes stay mounted and one is hidden, rather than one
   being unmounted: switching modes must not discard text the user has typed, and an
   unmounted editor would take its visible text with it. `document` hides the claim
   column the same way, which is also what makes approval reachable on a narrow screen
   where the preview pane never sits beside anything. */
export const DraftWorkspace = ({ editor, mode, preview }: DraftWorkspaceProps) => (
  <div className="flex flex-col gap-6 lg:flex-row lg:items-start lg:gap-8 xl:gap-10">
    <div className={cx("min-w-0 flex-col gap-6", mode === "document" ? "hidden" : "flex lg:flex-1 lg:basis-7/12")}>
      {editor}
    </div>

    <div
      className={cx(
        "min-w-0 flex-col gap-5",
        /* `document` is the whole width, not the narrow column the split gives it: with
           the claims hidden there is nothing beside it to make room for. */
        mode === "document" ? "flex w-full" : "hidden lg:sticky lg:top-20 lg:flex lg:flex-1 lg:basis-5/12",
      )}
    >
      {preview}
    </div>
  </div>
);
