import type { ReactNode } from "react";

import { Card } from "../../ui/Card";
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
    <Card className="flex flex-wrap items-center justify-between gap-3 bg-cv-surface px-4 py-3 shadow-surface">
      <div>
        <p className="text-support font-bold text-cv-text">סביבת העבודה</p>
        <p className="mt-0.5 text-support text-cv-text-muted">
          אפשר לקרוא ולאשר, לתקן שורה בעזרת אייקון העריכה שלה, או לראות את המסמך המלא.
        </p>
      </div>
      <ViewSwitch
        label="בחירת תצוגת סביבת העבודה"
        onChange={onModeChange}
        options={[
          { label: "קריאה ואישור", value: "read" },
          { label: "מסמך בלבד", value: "document" },
        ]}
        value={mode}
      />
    </Card>

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
