import type { ReactNode } from "react";

import { cx } from "@/ui/cx";
import { ViewSwitch } from "@/ui/ViewSwitch";

/* What the screen is for at this moment. `read` is the lines, each with its own editing
   controls. `document` is the rendered document at the workspace's full width, with the
   template, the page count and the check beside it - the preview, at every width.

   The desktop used to set the two side by side in `read`. Its design gives that width to
   the section list and the fit card instead, and the rendered page squeezed into a
   third of what was left was too small to read anyway; the masthead's switch is one press
   away from it. */
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

/* The mode switch, the desktop's way to the preview. A phone has `DraftPreviewToggle`
   in its compact header instead, so the page draws this from `lg` only. */
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
      { label: "עריכה", value: "read" },
      { label: "תצוגה מקדימה", value: "document" },
    ]}
    value={mode}
  />
);

/* Both panes stay mounted and one is hidden, rather than one being unmounted: switching
   modes must not discard text the user has typed, and an unmounted editor would take its
   visible text with it. One pane at a time at every width - see `DraftWorkspaceMode`. */
export const DraftWorkspace = ({ editor, mode, preview }: DraftWorkspaceProps) => (
  /* The step grid's wide column from the large breakpoint, beside the fit card. */
  <div className="flex flex-col gap-6 lg:col-span-1! lg:col-start-1!">
    <div className={cx("min-w-0 flex-col gap-6", mode === "document" ? "hidden" : "flex")}>{editor}</div>

    <div className={cx("min-w-0 flex-col gap-5", mode === "document" ? "flex w-full" : "hidden")}>{preview}</div>
  </div>
);
