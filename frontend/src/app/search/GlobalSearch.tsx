import { Search } from "lucide-react";
import { useEffect, useState } from "react";

import { GlobalSearchDialog } from "./GlobalSearchDialog";

/* Typing "k" while composing text - with a modifier held incidentally, as some IME and
   emoji-picker chords do - must not pull focus out of the field into the dialog. */
const isTypingTarget = (target: EventTarget | null): boolean => {
  if (!(target instanceof HTMLElement)) {
    return false;
  }
  return target.isContentEditable || ["INPUT", "TEXTAREA", "SELECT"].includes(target.tagName);
};

/* The palette and the two ways in: the trigger the header shows and the shortcut that
   works anywhere. Both live here so the header composes one element and holds no state
   about a dialog it does not otherwise know. */
export const GlobalSearch = () => {
  const [open, setOpen] = useState(false);

  useEffect(() => {
    const handleKeyDown = (event: KeyboardEvent) => {
      if (!(event.metaKey || event.ctrlKey) || (event.key !== "k" && event.key !== "K")) {
        return;
      }
      if (isTypingTarget(event.target)) {
        return;
      }
      event.preventDefault();
      setOpen((previous) => !previous);
    };

    window.addEventListener("keydown", handleKeyDown);
    return () => {
      window.removeEventListener("keydown", handleKeyDown);
    };
  }, []);

  return (
    <>
      <button
        aria-label="חיפוש מהיר של מועמדויות (Cmd+K)"
        className="inline-flex items-center gap-2 rounded-control border border-cv-border bg-cv-surface-muted px-3 py-1.5 text-support text-cv-text-muted transition-colors hover:border-cv-border-strong hover:bg-cv-surface hover:text-cv-text"
        onClick={() => setOpen(true)}
        type="button"
      >
        <Search aria-hidden="true" className="size-4 shrink-0 text-cv-accent" />
        <span className="hidden md:inline">חיפוש מהיר…</span>
        <kbd className="hidden rounded border border-cv-border bg-cv-surface px-1.5 py-0.5 text-support font-mono text-cv-text-muted sm:inline-block">
          ⌘K
        </kbd>
      </button>

      <GlobalSearchDialog onClose={() => setOpen(false)} open={open} />
    </>
  );
};
