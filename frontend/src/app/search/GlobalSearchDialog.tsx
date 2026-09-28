import { CircleAlert, Plus, Search, X } from "lucide-react";
import { type KeyboardEvent, type ReactNode, useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";

import type { ApplicationListItem } from "@/api/contracts";
import { ApplicationSummary } from "@/features/application-list";
import { preparationResumeDestination } from "@/features/preparation";
import { Button } from "@/ui/Button";
import { cx } from "@/ui/cx";
import { wrapDialogFocus } from "@/ui/dialogFocus";
import { LiveRegion } from "@/ui/LiveRegion";
import { routePaths } from "../routePaths";
import { type ApplicationSearch, useApplicationSearch } from "./useApplicationSearch";

/* oxlint-disable jsx-a11y/no-noninteractive-element-interactions */

interface GlobalSearchDialogProps {
  onClose: () => void;
  open: boolean;
}

const LISTBOX_ID = "global-search-results";
const optionId = (item: ApplicationListItem): string => `global-search-result-${item.id}`;

const Kbd = ({ children, className }: { children: ReactNode; className?: string }) => (
  <kbd className={cx("rounded border border-cv-border px-1.5 py-0.5 text-support font-mono", className)}>
    {children}
  </kbd>
);

/* Command palette: find an Application and navigate to it. Uses native <dialog> directly
   (not `ui/Dialog`) because its whole surface is one combobox that owns focus. */
export const GlobalSearchDialog = ({ onClose, open }: GlobalSearchDialogProps) => {
  const navigate = useNavigate();
  const dialogRef = useRef<HTMLDialogElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const [activeIndex, setActiveIndex] = useState(0);
  const results = useApplicationSearch(open);
  const { items, isStale, search, setSearch } = results;

  // Clamped: a new result set may be shorter than the one the index was chosen in.
  const active = Math.min(activeIndex, items.length - 1);
  const activeItem = active >= 0 ? items[active] : undefined;

  useEffect(() => {
    const dialog = dialogRef.current;
    if (dialog === null) {
      return;
    }

    if (open && !dialog.open) {
      dialog.showModal();
      inputRef.current?.focus();
      return;
    }

    // Close via the element (not unmount) so focus returns to the invoker.
    if (!open && dialog.open) {
      dialog.close();
    }
  }, [open]);

  const updateSearch = (value: string) => {
    setSearch(value);
    setActiveIndex(0);
  };

  const moveTo = (index: number) => {
    setActiveIndex(index);
    const item = items[index];
    if (item !== undefined) {
      dialogRef.current?.ownerDocument.getElementById(optionId(item))?.scrollIntoView?.({ block: "nearest" });
    }
  };

  const selectItem = (item: ApplicationListItem) => {
    onClose();
    void navigate(preparationResumeDestination(item));
  };

  // Escape is left to the dialog's native cancel behavior.
  const handleKeyDown = (event: KeyboardEvent<HTMLInputElement>) => {
    if (items.length === 0 || event.nativeEvent.isComposing) {
      return;
    }

    const last = items.length - 1;
    switch (event.key) {
      case "ArrowDown":
        event.preventDefault();
        moveTo(active >= last ? 0 : active + 1);
        break;
      case "ArrowUp":
        event.preventDefault();
        moveTo(active <= 0 ? last : active - 1);
        break;
      case "Enter":
        event.preventDefault();
        // Never act on rows left over from the previous search text.
        if (activeItem !== undefined && !isStale) {
          selectItem(activeItem);
        }
        break;
    }
  };

  return (
    <dialog
      // `open:flex` only: an unconditional `flex` would override the closed dialog's `display: none`.
      // Centred by `inset-x-0 mx-auto`: with a fixed width in RTL, `left` loses to the UA's `right: 0`.
      aria-label="מעבר מהיר למועמדות"
      className="fixed inset-x-0 top-24 bottom-auto mx-auto my-0 hidden open:flex max-h-[75vh] w-[calc(100%-2rem)] max-w-2xl flex-col rounded-surface border border-cv-border bg-cv-surface p-0 text-cv-text shadow-floating backdrop:bg-cv-text/40 backdrop:backdrop-blur-sm"
      onClick={(event) => {
        if (event.target === event.currentTarget) {
          onClose();
        }
      }}
      onKeyDown={wrapDialogFocus}
      onClose={(event) => {
        // Keep the close event from also dismissing an owning dialog.
        event.stopPropagation();
        updateSearch("");
        onClose();
      }}
      ref={dialogRef}
    >
      <div className="flex items-center gap-3 border-b border-cv-border px-4 py-3">
        <Search aria-hidden="true" className="size-icon-lg shrink-0 text-cv-accent" />
        <input
          aria-activedescendant={activeItem === undefined ? undefined : optionId(activeItem)}
          aria-autocomplete="list"
          aria-controls={LISTBOX_ID}
          aria-expanded={items.length > 0}
          aria-label="חיפוש מועמדות"
          autoComplete="off"
          className="flex-1 bg-transparent text-body font-medium text-cv-text placeholder:text-cv-text-muted focus:ring-0"
          dir="auto"
          id="global-search-input"
          name="global-search"
          onChange={(event) => updateSearch(event.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="חברה, תפקיד או מילת מפתח…"
          ref={inputRef}
          role="combobox"
          type="text"
          value={search}
        />
        {search === "" ? null : (
          <button
            aria-label="ניקוי חיפוש"
            className="rounded-control p-1 text-cv-text-muted hover:bg-cv-surface-muted hover:text-cv-text"
            onClick={() => {
              updateSearch("");
              inputRef.current?.focus();
            }}
            type="button"
          >
            <X aria-hidden="true" className="size-icon-md" />
          </button>
        )}
        <Kbd className="hidden bg-cv-surface-muted text-cv-text-muted sm:inline-block">ESC</Kbd>
      </div>

      <div className="max-h-[60vh] overflow-y-auto p-2">
        <ResultsStatus results={results} />
        <LiveRegion>{announcement(results)}</LiveRegion>

        <div
          aria-label={results.mode.kind === "attention" ? "דורש טיפול" : "תוצאות חיפוש"}
          className={cx("transition-opacity", isStale && "opacity-60")}
          id={LISTBOX_ID}
          // oxlint-disable-next-line jsx-a11y/prefer-tag-over-role
          role="listbox"
        >
          {results.isError
            ? null
            : items.map((item, index) => (
                // Keyboard selection is owned by the combobox; options never take focus.
                // oxlint-disable-next-line jsx-a11y/click-events-have-key-events
                <div
                  aria-selected={index === active}
                  className={cx(
                    "flex cursor-pointer items-center justify-between gap-3 rounded-control border p-3 transition-colors",
                    index === active ? "border-cv-accent/40 bg-cv-accent-soft" : "border-transparent",
                  )}
                  id={optionId(item)}
                  key={item.id}
                  onClick={() => selectItem(item)}
                  onMouseDown={(event) => event.preventDefault()}
                  // Move, not enter: keyboard scrolling must not let a resting pointer steal selection.
                  onMouseMove={() => {
                    if (index !== active) setActiveIndex(index);
                  }}
                  // oxlint-disable-next-line jsx-a11y/prefer-tag-over-role
                  role="option"
                  tabIndex={-1}
                >
                  <ApplicationSummary item={item} />
                </div>
              ))}
        </div>
      </div>

      <div className="flex flex-wrap items-center justify-between gap-2 border-t border-cv-border bg-cv-surface-muted/60 px-4 py-2.5 text-support text-cv-text-muted">
        <button
          className="inline-flex items-center gap-1.5 font-medium text-cv-accent hover:underline"
          onClick={() => {
            onClose();
            void navigate(routePaths.newApplication);
          }}
          type="button"
        >
          <Plus aria-hidden="true" className="size-icon-sm" />
          משרה חדשה
        </button>

        <div className="hidden items-center gap-2 sm:flex">
          <span>ניווט במקשים:</span>
          <Kbd className="bg-cv-surface px-1 py-0">↑↓</Kbd>
          <span>לבחירה:</span>
          <Kbd className="bg-cv-surface px-1 py-0">Enter</Kbd>
        </div>
      </div>
    </dialog>
  );
};

const announcement = ({ isError, isPending, isStale, items }: ApplicationSearch): string | null => {
  if (isError || isPending || isStale) {
    return null;
  }
  return items.length === 0 ? "אין תוצאות" : `${items.length} תוצאות`;
};

const ResultsStatus = ({ results }: { results: ApplicationSearch }) => {
  const { isError, isPending, isStale, items, mode, retry } = results;

  if (isError) {
    return (
      <div className="flex flex-col items-center gap-3 py-10 text-center">
        <p className="font-semibold text-cv-blocker" role="alert">
          החיפוש נכשל.
        </p>
        <Button onClick={retry} variant="secondary">
          ניסיון חוזר
        </Button>
      </div>
    );
  }

  if (items.length > 0) {
    return mode.kind === "attention" && !isStale ? (
      <p aria-hidden="true" className="px-3 py-1.5 text-support font-semibold text-cv-text-muted">
        דורש טיפול
      </p>
    ) : null;
  }

  if (isPending || isStale) {
    return <p className="py-10 text-center text-cv-text-muted">מחפש…</p>;
  }

  return (
    <div className="py-10 text-center">
      <CircleAlert aria-hidden="true" className="mx-auto mb-3 size-7 text-cv-border-strong" />
      {mode.kind === "attention" ? (
        <>
          <p className="font-semibold text-cv-text">שום מועמדות לא ממתינה לטיפול</p>
          <p className="mt-1 text-support text-cv-text-muted">אפשר לחפש לפי חברה או תפקיד, או לקלוט משרה חדשה.</p>
        </>
      ) : (
        <>
          <p className="font-semibold text-cv-text">אין מועמדות שתואמת ל&quot;{mode.text}&quot;</p>
          <p className="mt-1 text-support text-cv-text-muted">אפשר לנסות מילת חיפוש אחרת או לקלוט משרה חדשה.</p>
        </>
      )}
    </div>
  );
};
