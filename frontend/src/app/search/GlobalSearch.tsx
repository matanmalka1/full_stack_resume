import { Search } from "lucide-react";
import { useEffect, useState } from "react";

import { cx } from "@/ui/cx";

import { GlobalSearchDialog } from "./GlobalSearchDialog";

/* Typing "k" while composing text - with a modifier held incidentally, as some IME and
   emoji-picker chords do - must not pull focus out of the field into the dialog. */
const isTypingTarget = (target: EventTarget | null): boolean => {
  if (!(target instanceof HTMLElement)) {
    return false;
  }
  return target.isContentEditable || ["INPUT", "TEXTAREA", "SELECT"].includes(target.tagName);
};

/* The palette and the two ways in: the trigger the shell shows and the shortcut that
   works anywhere. Both live here so the shell composes one element and holds no state
   about a dialog it does not otherwise know.

   The trigger takes the shell's two shapes: a round search button in a phone's top bar,
   and from the large breakpoint a search field in the sidebar that names the shortcut. */
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
        aria-keyshortcuts="Meta+K Control+K"
        aria-label="מעבר מהיר למועמדות"
        className={cx(
          "flex shrink-0 items-center border border-cv-border transition-colors hover:border-cv-border-strong",
          "size-11 justify-center rounded-control bg-cv-surface text-cv-accent",
          "lg:h-10 lg:w-full lg:justify-start lg:gap-2 lg:rounded-control-sm lg:bg-cv-field-background lg:px-3 lg:text-label lg:text-cv-text-muted lg:hover:text-cv-text",
        )}
        onClick={() => setOpen(true)}
        type="button"
      >
        <Search aria-hidden="true" className="size-4.5 shrink-0 lg:size-icon-md" />
        <span className="hidden flex-1 truncate text-start lg:inline">מעבר מהיר…</span>
        <kbd className="hidden rounded-sm border border-cv-border bg-cv-surface px-1.5 font-sans text-caption text-cv-text-muted lg:inline-block">
          ⌘K
        </kbd>
      </button>

      <GlobalSearchDialog onClose={() => setOpen(false)} open={open} />
    </>
  );
};
