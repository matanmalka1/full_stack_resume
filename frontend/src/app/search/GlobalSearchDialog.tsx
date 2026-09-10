import { useQuery } from "@tanstack/react-query";
import { CircleAlert, Plus, Search, X } from "lucide-react";
import { type KeyboardEvent, useDeferredValue, useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";

import { applicationListQueryOptions } from "@/api/applications";
import type { ApplicationListItem } from "@/api/contracts";
import { ApplicationSummary } from "@/features/application-list";
import { preparationResumeDestination } from "@/features/preparation";
import { cx } from "@/ui/cx";
import { routePaths } from "../routePaths";

/* Native <dialog> backdrop clicks are valid interaction; Escape is handled by the
   element's built-in cancel behavior. */
/* oxlint-disable jsx-a11y/no-noninteractive-element-interactions */

interface GlobalSearchDialogProps {
  onClose: () => void;
  open: boolean;
}

const LISTBOX_ID = "global-search-results";
const optionId = (item: ApplicationListItem): string => `global-search-result-${item.id}`;

/* Find an Application from anywhere and go to it. The palette navigates; it does not
   manage records, so it is not a second board - the board's own filters, actions, and
   pagination stay there, and a result here is drawn by the board's own summary. */
export const GlobalSearchDialog = ({ onClose, open }: GlobalSearchDialogProps) => {
  const navigate = useNavigate();
  const [search, setSearch] = useState("");
  const [selectedIndex, setSelectedIndex] = useState(0);
  const inputRef = useRef<HTMLInputElement>(null);
  const dialogRef = useRef<HTMLDialogElement>(null);

  const trimmed = search.trim();
  /* The query, not this client, decides what counts as a match - the server's `search`
     narrows the same way the board's own search box does. Deferred so a fast typist keeps
     a responsive input while the fetch it triggers settles a beat behind. */
  const deferredSearch = useDeferredValue(trimmed);

  /* Empty query: the board's own "needs_attention" preset, so the palette opens on the
     same answer to "what needs me" the board already gives rather than an arbitrary
     recency slice. Typing replaces that question with the server's free-text search. */
  const query = useQuery({
    ...applicationListQueryOptions(
      deferredSearch === "" ? { preset: "needs_attention", limit: 8 } : { search: deferredSearch, limit: 8 },
    ),
    enabled: open,
  });
  const items = query.data?.items ?? [];
  const selected = items[selectedIndex];

  /* Opening is also what resets the palette: the previous search is a transient answer to
     a question already asked, and reopening on it would hide the "what needs me" list the
     empty state is for. */
  useEffect(() => {
    const dialog = dialogRef.current;
    if (!open || dialog === null || dialog.open) {
      return;
    }

    // Opening a native dialog synchronizes this transient UI with the `open` prop.
    // oxlint-disable-next-line react/set-state-in-effect
    setSearch("");
    setSelectedIndex(0);
    dialog.showModal();
    inputRef.current?.focus();
  }, [open]);

  const selectItem = (item: ApplicationListItem) => {
    onClose();
    void navigate(preparationResumeDestination(item));
  };

  const handleKeyDown = (event: KeyboardEvent<HTMLInputElement>) => {
    if (event.key === "Escape") {
      onClose();
      return;
    }

    if (items.length === 0) {
      return;
    }

    if (event.key === "ArrowDown") {
      event.preventDefault();
      setSelectedIndex((previous) => (previous + 1) % items.length);
    } else if (event.key === "ArrowUp") {
      event.preventDefault();
      setSelectedIndex((previous) => (previous - 1 + items.length) % items.length);
    } else if (event.key === "Enter") {
      event.preventDefault();
      if (selected !== undefined) {
        selectItem(selected);
      }
    }
  };

  if (!open) {
    return null;
  }

  return (
    <dialog
      aria-label="מעבר מהיר למועמדות"
      className="fixed left-1/2 top-24 m-0 flex max-h-[75vh] w-[calc(100%-2rem)] max-w-2xl -translate-x-1/2 flex-col rounded-surface border border-cv-border bg-cv-surface p-0 text-cv-text shadow-floating backdrop:bg-cv-text/40 backdrop:backdrop-blur-sm"
      onClick={(event) => {
        if (event.target === dialogRef.current) {
          onClose();
        }
      }}
      onKeyDown={() => undefined}
      onClose={onClose}
      ref={dialogRef}
    >
      <div className="flex items-center gap-3 border-b border-cv-border px-4 py-3">
        <Search aria-hidden="true" className="size-5 shrink-0 text-cv-accent" />
        <input
          aria-activedescendant={selected === undefined ? undefined : optionId(selected)}
          aria-autocomplete="list"
          aria-controls={LISTBOX_ID}
          aria-expanded="true"
          className="flex-1 bg-transparent text-body font-medium text-cv-text placeholder:text-cv-text-muted focus:ring-0"
          dir="auto"
          onChange={(event) => {
            setSearch(event.target.value);
            setSelectedIndex(0);
          }}
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
              setSearch("");
              setSelectedIndex(0);
              inputRef.current?.focus();
            }}
            type="button"
          >
            <X aria-hidden="true" className="size-4" />
          </button>
        )}
        <kbd className="hidden rounded border border-cv-border bg-cv-surface-muted px-1.5 py-0.5 text-support font-mono text-cv-text-muted sm:inline-block">
          ESC
        </kbd>
      </div>

      {/* Custom JS-driven combobox (ARIA authoring-practices pattern): rich item content
          and keyboard-managed selection that a native <select>/<option> can't render. */}
      {/* oxlint-disable-next-line jsx-a11y/prefer-tag-over-role */}
      <div className="max-h-[60vh] overflow-y-auto p-2" id={LISTBOX_ID} role="listbox">
        {trimmed === "" && items.length > 0 ? (
          <p className="px-3 py-1.5 text-support font-semibold text-cv-text-muted">דורש טיפול</p>
        ) : null}

        {query.isError ? (
          <p className="py-10 text-center font-semibold text-cv-blocker" role="alert">
            החיפוש נכשל. אפשר לנסות שוב בעוד רגע.
          </p>
        ) : items.length === 0 && query.isPending ? (
          <p className="py-10 text-center text-cv-text-muted">מחפש…</p>
        ) : items.length === 0 ? (
          <div className="py-10 text-center">
            <CircleAlert aria-hidden="true" className="mx-auto mb-3 size-7 text-cv-border-strong" />
            {trimmed === "" ? (
              <>
                <p className="font-semibold text-cv-text">שום מועמדות לא ממתינה לטיפול</p>
                <p className="mt-1 text-support text-cv-text-muted">אפשר לחפש לפי חברה או תפקיד, או לקלוט משרה חדשה.</p>
              </>
            ) : (
              <>
                <p className="font-semibold text-cv-text">אין מועמדות שתואמת ל&quot;{trimmed}&quot;</p>
                <p className="mt-1 text-support text-cv-text-muted">אפשר לנסות מילת חיפוש אחרת או לקלוט משרה חדשה.</p>
              </>
            )}
          </div>
        ) : (
          items.map((item, index) => (
            <div
              aria-selected={index === selectedIndex}
              className={cx(
                "flex cursor-pointer items-center justify-between gap-3 rounded-control border p-3 transition-colors",
                index === selectedIndex
                  ? "border-cv-accent/40 bg-cv-accent-soft"
                  : "border-transparent hover:bg-cv-surface-muted",
              )}
              id={optionId(item)}
              key={item.id}
              onClick={() => selectItem(item)}
              onKeyDown={(event) => {
                if (event.key === "Enter" || event.key === " ") selectItem(item);
              }}
              onMouseEnter={() => setSelectedIndex(index)}
              // Same combobox pattern as the listbox above: rich item content a native
              // <option> can't render.
              // oxlint-disable-next-line jsx-a11y/prefer-tag-over-role
              role="option"
              tabIndex={-1}
            >
              <ApplicationSummary item={item} />
            </div>
          ))
        )}
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
          <Plus aria-hidden="true" className="size-3.5" />
          משרה חדשה
        </button>

        <div className="hidden items-center gap-2 sm:flex">
          <span>ניווט במקשים:</span>
          <kbd className="rounded border border-cv-border bg-cv-surface px-1 text-support font-mono">↑↓</kbd>
          <span>לבחירה:</span>
          <kbd className="rounded border border-cv-border bg-cv-surface px-1 text-support font-mono">Enter</kbd>
        </div>
      </div>
    </dialog>
  );
};
