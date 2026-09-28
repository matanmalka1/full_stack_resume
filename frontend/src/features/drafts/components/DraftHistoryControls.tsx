import { Redo2, Undo2 } from "lucide-react";
import { useEffect } from "react";

import { Button } from "@/ui/Button";
import { Tooltip } from "@/ui/Tooltip";

interface DraftHistoryControlsProps {
  canRedo: boolean;
  canUndo: boolean;
  onRedo: () => void;
  onUndo: () => void;
}

export const DraftHistoryControls = ({ canRedo, canUndo, onRedo, onUndo }: DraftHistoryControlsProps) => {
  useEffect(() => {
    const onKeyDown = (event: KeyboardEvent) => {
      if (!(event.metaKey || event.ctrlKey) || event.altKey) return;
      const key = event.key.toLowerCase();
      const target = event.target;
      if (
        target instanceof HTMLElement &&
        (target.matches("input, textarea, [contenteditable=true]") || target.isContentEditable) &&
        target.getAttribute("aria-label") !== "טקסט השורה"
      ) {
        return;
      }
      const redo = key === "y" || (key === "z" && event.shiftKey);
      if (redo) {
        if (!canRedo) return;
        event.preventDefault();
        onRedo();
      } else {
        if (key !== "z") return;
        if (!canUndo) return;
        event.preventDefault();
        onUndo();
      }
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [canRedo, canUndo, onRedo, onUndo]);

  /* Two icon buttons beside the outline's heading. Their shortcuts and the history's
     depth are in the tooltips: a sentence about fifty remembered changes was a line of
     its own on every visit, for something the reader only needs when reaching for it. */
  return (
    <div aria-label="היסטוריית עריכת הטיוטה" className="flex items-center gap-1" role="toolbar">
      <Tooltip label="ביטול השינוי האחרון (Ctrl/⌘+Z). נשמרים עד 50 שינויי ניסוח וסדר." wrap>
        <Button aria-label="ביטול השינוי האחרון" disabled={!canUndo} onClick={onUndo} variant="secondary">
          <Undo2 aria-hidden="true" className="size-icon-md" />
        </Button>
      </Tooltip>
      <Tooltip label="החזרת השינוי שבוטל (Ctrl+Y או ⌘+Shift+Z)" wrap>
        <Button aria-label="החזרת השינוי שבוטל" disabled={!canRedo} onClick={onRedo} variant="secondary">
          <Redo2 aria-hidden="true" className="size-icon-md" />
        </Button>
      </Tooltip>
    </div>
  );
};
