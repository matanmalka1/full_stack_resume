import { Eye, PenLine } from "lucide-react";

import { cx } from "@/ui/cx";
import type { DraftWorkspaceMode } from "./DraftWorkspace";

/* The one switch between the draft's lines and the whole rendered document, in the
   heading's row at every width: an outlined, labelled button on a wide screen and a bare
   44px icon in a phone's top bar. Its name is what a press does - see the document, or go
   back to its lines - and the same at both widths, so the label is hidden on a phone
   rather than swapped for another.

   It changes `mode` through the page's handler, so leaving the lines still settles the
   autosave buffer first. A toggle button, not a link: the route stays the editor's. */
export const DraftPreviewToggle = ({
  mode,
  onModeChange,
}: {
  mode: DraftWorkspaceMode;
  onModeChange: (mode: DraftWorkspaceMode) => void;
}) => {
  const previewing = mode === "document";
  const Icon = previewing ? PenLine : Eye;
  return (
    <button
      aria-pressed={previewing}
      className={cx(
        "inline-flex shrink-0 items-center justify-center gap-1.5 rounded-control font-bold text-cv-text transition-colors duration-200",
        "h-11 border border-cv-border-strong bg-cv-surface px-3.5 text-label hover:bg-cv-surface-muted",
        "max-lg:w-11 max-lg:border-0 max-lg:bg-transparent max-lg:px-0",
      )}
      onClick={() => onModeChange(previewing ? "read" : "document")}
      type="button"
    >
      <Icon aria-hidden="true" className="size-icon-lg lg:size-icon-md" />
      <span className="max-lg:sr-only">תצוגה מקדימה</span>
    </button>
  );
};
