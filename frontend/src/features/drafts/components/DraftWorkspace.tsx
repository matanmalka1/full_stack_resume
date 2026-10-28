import type { ReactNode } from "react";

import { cx } from "@/ui/cx";
import { ViewSwitch } from "@/ui/ViewSwitch";

/* What the screen is for at this moment.

   `split` is the default: the lines beside the rendered document, so an edit and its
   effect on the page - the template, the page count, the check - are read together. A
   phone has no room for two panes and shows the lines alone, which is why the default
   reads as the rows there. `read` is the lines alone at every width, for a desktop reader
   who wants the section list and the fit card beside them instead (the desktop design's
   own layout). `document` is the rendered document at the workspace's full width. */
export type DraftWorkspaceMode = "split" | "read" | "document";

interface DraftWorkspaceProps {
  /* The claim column: the draft as rows, each with its own editing controls. */
  editor: ReactNode;
  /* Chosen by `DraftWorkspaceSwitch`, which the page places; switching to `document`
     settles the autosave buffer first, which is the page's business rather than the
     layout's. */
  mode: DraftWorkspaceMode;
  preview: ReactNode;
}

/* The mode switch, the desktop's three layouts. A phone has `DraftPreviewToggle` in its
   compact header instead - rows or document, the two its one pane can show - so the page
   draws this from `lg` only. */
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
      { label: "עריכה ותצוגה", value: "split" },
      { label: "עריכה", value: "read" },
      { label: "תצוגה מקדימה", value: "document" },
    ]}
    value={mode}
  />
);

/* Both panes stay mounted and the one not shown is hidden, rather than unmounted:
   switching modes must not discard text the user has typed, and an unmounted editor would
   take its visible text with it.

   In `split` the workspace takes the step grid's whole width, with the fit card above
   the workspace (see `DraftFitCard`): the lines, their section list and the document
   already fill the row. In `read` and `document` it is the grid's wide column, beside the fit card. */
export const DraftWorkspace = ({ editor, mode, preview }: DraftWorkspaceProps) => (
  <div
    className={cx(
      "flex flex-col gap-6",
      mode === "split" ? "lg:flex-row lg:items-start lg:gap-8 xl:gap-10" : "lg:col-span-1! lg:col-start-1!",
    )}
  >
    <div
      className={cx(
        "min-w-0 flex-col gap-6",
        mode === "document" ? "hidden" : "flex",
        mode === "split" && "lg:flex-1 lg:basis-7/12",
      )}
    >
      {editor}
    </div>

    <div
      className={cx(
        "min-w-0 flex-col gap-5",
        mode === "document"
          ? "flex w-full"
          : mode === "split"
            ? "hidden lg:sticky lg:top-6 lg:flex lg:flex-1 lg:basis-5/12"
            : "hidden",
      )}
    >
      {preview}
    </div>
  </div>
);
