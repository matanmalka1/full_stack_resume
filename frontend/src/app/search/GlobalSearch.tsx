import { Search } from "lucide-react";
import { useEffect, useState } from "react";

import { cx } from "@/ui/cx";
import { Tooltip } from "@/ui/Tooltip";

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
   about a dialog it does not otherwise know.

   `compact` is the collapsed sidebar's icon-only trigger: the same button and shortcut,
   with the visible label moved into a tooltip beside the rail. */
export const GlobalSearch = ({
  className,
  compact = false,
  showTrigger = true,
}: {
  className?: string;
  compact?: boolean;
  showTrigger?: boolean;
}) => {
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

  const trigger = (
    <button
      aria-keyshortcuts="Meta+K Control+K"
      aria-label="מעבר מהיר למועמדות"
      className={cx(
        "inline-flex items-center rounded-control border border-cv-border bg-cv-surface-muted text-cv-text-muted transition-colors hover:border-cv-border-strong hover:bg-cv-surface hover:text-cv-text",
        compact ? "size-11 justify-center" : "min-h-11 gap-2 px-3 text-support",
        className,
      )}
      onClick={() => setOpen(true)}
      type="button"
    >
      <Search aria-hidden="true" className="size-icon-md shrink-0 text-cv-accent" />
      {!compact && (
        <>
          <span className="hidden truncate md:inline">מעבר מהיר…</span>
          <kbd className="hidden rounded border border-cv-border bg-cv-surface px-1.5 py-0.5 text-support font-mono text-cv-text-muted sm:inline-block">
            ⌘K
          </kbd>
        </>
      )}
    </button>
  );

  return (
    <>
      {showTrigger &&
        (compact ? (
          <Tooltip label="מעבר מהיר (⌘K)" placement="rail">
            {trigger}
          </Tooltip>
        ) : (
          trigger
        ))}

      <GlobalSearchDialog onClose={() => setOpen(false)} open={open} />
    </>
  );
};
