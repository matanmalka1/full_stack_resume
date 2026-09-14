import { Redo2, Undo2 } from "lucide-react";
import { useEffect } from "react";

import { Button } from "@/ui/Button";

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

  return (
    <div aria-label="היסטוריית עריכת הטיוטה" className="flex flex-wrap items-center gap-2" role="toolbar">
      <Button disabled={!canUndo} onClick={onUndo} title="ביטול השינוי האחרון (Ctrl/⌘+Z)" variant="secondary">
        <Undo2 aria-hidden="true" className="size-icon-md" />
        ביטול
      </Button>
      <Button disabled={!canRedo} onClick={onRedo} title="החזרת השינוי שבוטל (Ctrl+Y או ⌘+Shift+Z)" variant="secondary">
        <Redo2 aria-hidden="true" className="size-icon-md" />
        ביצוע מחדש
      </Button>
      <span className="text-support text-cv-text-muted">נשמרים עד 50 שינויי ניסוח וסדר בטיוטה הזו.</span>
    </div>
  );
};
