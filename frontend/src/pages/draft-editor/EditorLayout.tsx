import type { ReactNode } from "react";

import { cx } from "../../ui/cx";
import { ViewSwitch } from "../../ui/ViewSwitch";

/* What the screen is for at this moment.

   The switch used to choose a layout - editor, split, preview - while the claims below it
   were always editable, so a screen opened to read a document and sign it opened as a page
   of sixty textareas. There is no screen-wide editing mode now: `read` shows the draft as
   text with the facts behind each line and a pencil on every row, and `document` drops the
   rows for the rendered preview alone. Changing one line is a decision about that line. */
export type EditorMode = "read" | "document";

interface EditorLayoutProps {
  /* The claim column: the draft as rows, each with its own editing controls. */
  editor: ReactNode;
  mode: EditorMode;
  /* Owned upstream: the page builds the claim handlers from it, so it cannot live here. */
  onModeChange: (mode: EditorMode) => void;
  preview: ReactNode;
}

/* A.4's responsive fallback. Both panes stay mounted and one is hidden, rather than one
   being unmounted: switching modes must not discard text the user has typed, and an
   unmounted editor would take its visible text with it. `document` hides the claim
   column the same way, which is also what makes approval reachable on a narrow screen
   where the preview pane never sits beside anything. */
export const EditorLayout = ({ editor, mode, onModeChange, preview }: EditorLayoutProps) => (
  <div className="flex flex-col gap-6">
    {/* The switch alone, on its own line. It used to sit in a titled card explaining what
        the two options do - a heading, a sentence, and a surface, all above the document,
        to caption a control whose two labels already say it. On a screen that already
        spends its first six hundred pixels on breadcrumbs, a stepper, a heading and a
        header card, that was one band of furniture the reader scrolled past every visit. */}
    <div className="flex justify-end">
      <ViewSwitch
        label="בחירת תצוגת סביבת העבודה"
        onChange={onModeChange}
        options={[
          { label: "קריאה ואישור", value: "read" },
          { label: "מסמך בלבד", value: "document" },
        ]}
        value={mode}
      />
    </div>

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
  </div>
);
