import type { ReactNode } from "react";
import { useState } from "react";

import { cx } from "../../ui/cx";
import { ViewSwitch } from "../../ui/ViewSwitch";

type EditorView = "editor" | "split" | "preview";

/* A.4's responsive fallback. Both panes stay mounted and one is hidden, rather than one
   being unmounted: switching views must not discard text the user has typed, and an
   unmounted editor would take its visible text with it. */
export const EditorLayout = ({ editor, preview }: { editor: ReactNode; preview: ReactNode }) => {
  const [view, setView] = useState<EditorView>("split");

  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-wrap items-center justify-between gap-3 rounded-surface border border-cv-border bg-cv-surface px-4 py-3 shadow-surface">
        <div>
          <p className="text-support font-bold text-cv-text">סביבת העבודה</p>
          <p className="mt-0.5 text-support text-cv-text-muted">
            אפשר להתרכז בטקסט, להשוות למסמך או לעבור לתצוגה ולאישור.
          </p>
        </div>
        <ViewSwitch
          label="בחירת תצוגת סביבת העבודה"
          onChange={setView}
          options={[
            { label: "עריכה בלבד", value: "editor" },
            { label: "עריכה ותצוגה", value: "split" },
            { label: "תצוגה ואישור", value: "preview" },
          ]}
          value={view}
        />
      </div>

      <div
        className={cx(
          "flex flex-col gap-6",
          view === "split" ? "lg:flex-row lg:items-start lg:gap-8 xl:gap-10" : undefined,
        )}
      >
        <div
          className={cx(
            "min-w-0 flex-col gap-6",
            view === "preview" ? "hidden" : "flex",
            view === "split" ? "lg:flex-1 lg:basis-7/12" : undefined,
          )}
        >
          {editor}
        </div>

        <div
          className={cx(
            "min-w-0 flex-col gap-5",
            view === "editor" ? "hidden" : view === "split" ? "hidden lg:flex" : "flex",
            view === "split" ? "lg:sticky lg:top-20 lg:flex-1 lg:basis-5/12" : undefined,
          )}
        >
          {preview}
        </div>
      </div>
    </div>
  );
};
