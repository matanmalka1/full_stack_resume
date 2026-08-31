import type { ReactNode } from "react";
import { useState } from "react";

import { cx } from "../../ui/cx";
import { ViewSwitch } from "../../ui/ViewSwitch";

type EditorView = "editor" | "preview";

/* A.4's responsive fallback. Both panes stay mounted and one is hidden, rather than one
   being unmounted: switching views must not discard text the user has typed, and an
   unmounted editor would take its visible text with it. */
export const EditorLayout = ({
  editor,
  preview,
}: {
  editor: ReactNode;
  preview: ReactNode;
}) => {
  const [view, setView] = useState<EditorView>("editor");

  return (
    <div className="flex flex-col gap-6">
      <div className="lg:hidden">
        <ViewSwitch
          label="מעבר בין העריכה לתצוגה ולאישור"
          onChange={setView}
          /* The second pane is no longer only a preview: it carries the validation result
             and approval too, so at narrow widths its name includes everything it holds. */
          options={[
            { label: "עריכה", value: "editor" },
            { label: "תצוגה ואישור", value: "preview" },
          ]}
          value={view}
        />
      </div>

      <div className="flex flex-col gap-6 lg:flex-row lg:items-start lg:gap-8 xl:gap-10">
        <div
          className={cx(
            "flex min-w-0 flex-col gap-6 lg:flex-1 lg:basis-7/12",
            view === "editor" ? undefined : "hidden lg:flex",
          )}
        >
          {editor}
        </div>

        <div
          className={cx(
            "flex min-w-0 flex-col gap-5 lg:sticky lg:top-20 lg:flex-1 lg:basis-5/12",
            view === "preview" ? undefined : "hidden lg:flex",
          )}
        >
          {preview}
        </div>
      </div>
    </div>
  );
};
