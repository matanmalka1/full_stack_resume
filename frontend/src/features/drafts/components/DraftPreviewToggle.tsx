import { Eye, PenLine } from "lucide-react";

import { IconButton } from "@/ui/IconButton";
import type { DraftWorkspaceMode } from "./DraftWorkspace";

/* The phone's form of `DraftWorkspaceSwitch`: one icon in the step's compact header that
   flips between the rows and the whole rendered document. Below the large breakpoint the
   two never sit side by side, so the choice is one of two states rather than one of two
   labels, and a full segmented control under the heading spent a row on it.

   It changes `mode` through the same handler as the switch, so leaving the rows still
   settles the autosave buffer first. Back from the document is `split`, the default, which
   a phone shows as the rows. A toggle button, not a link: the route stays the editor's. */
export const DraftPreviewToggle = ({
  mode,
  onModeChange,
}: {
  mode: DraftWorkspaceMode;
  onModeChange: (mode: DraftWorkspaceMode) => void;
}) => {
  const previewing = mode === "document";
  return (
    <IconButton
      /* Named for what a press does, not as a pressed state of "תצוגה מלאה": the switch's
         own button carries that name in the same document, hidden on a phone but not
         from a query, and two controls answering to one name is one too many. */
      aria-label={previewing ? "חזרה לעריכת השורות" : "הצגת המסמך המלא"}
      className="lg:hidden"
      onClick={() => onModeChange(previewing ? "split" : "document")}
    >
      {previewing ? (
        <PenLine aria-hidden="true" className="size-icon-md" />
      ) : (
        <Eye aria-hidden="true" className="size-icon-md" />
      )}
    </IconButton>
  );
};
