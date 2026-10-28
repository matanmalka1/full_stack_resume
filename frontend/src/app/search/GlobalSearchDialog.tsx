import { CircleAlert, Plus, Search, X } from "lucide-react";
import { type KeyboardEvent, type ReactNode, useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";

import { ApplicationSummary } from "@/features/application-list";
import { factLabel, factStatusLabel } from "@/features/facts";
import { preparationResumeDestination } from "@/features/preparation";
import { ErrorCallout } from "@/ui/ErrorCallout";
import { Button } from "@/ui/Button";
import { IconButton } from "@/ui/IconButton";
import { cx } from "@/ui/cx";
import { DateTime } from "@/ui/DateTime";
import { wrapDialogFocus } from "@/ui/dialogFocus";
import { LiveRegion } from "@/ui/LiveRegion";
import { routePaths } from "@/navigation/routePaths";
import { type ApplicationSearch, type GlobalSearchItem, useApplicationSearch } from "./useApplicationSearch";

/* oxlint-disable jsx-a11y/no-noninteractive-element-interactions */

interface GlobalSearchDialogProps {
  onClose: () => void;
  open: boolean;
}

const LISTBOX_ID = "global-search-results";
const optionId = (item: GlobalSearchItem): string => `global-search-result-${item.kind}-${item.id}`;

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
  const shownApplicationCount = items.filter((item) => item.kind === "application").length;

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

  const selectItem = (item: GlobalSearchItem) => {
    onClose();
    if (item.kind === "application") {
      void navigate(preparationResumeDestination(item.item));
    } else if (item.kind === "fact") {
      void navigate(`${routePaths.facts}?fact=${encodeURIComponent(item.fact.fact_id)}`);
    } else {
      void navigate(
        `${routePaths.facts}?fact=${encodeURIComponent(item.event.fact_id)}&event=${encodeURIComponent(item.event.id)}`,
      );
    }
  };

  // Escape is left to the dialog's native cancel behavior.
  const handleKeyDown = (event: KeyboardEvent<HTMLInputElement>) => {
    if (items.length === 0 || results.isPending || results.isError || isStale || event.nativeEvent.isComposing) {
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
      // Below the large breakpoint it is the whole screen, as a phone's own search is: the
      // field pinned at the top with a cancel beside it, then the results and the new-job
      // row after them, scrolling as one column.
      className="fixed inset-x-0 top-24 bottom-auto mx-auto my-0 hidden open:flex max-h-[75vh] w-[calc(100%-2rem)] max-w-[42.5rem] flex-col overflow-hidden rounded-sheet border-0 bg-cv-surface p-0 text-cv-text shadow-overlay backdrop:bg-cv-text/40 backdrop:backdrop-blur-sm max-lg:inset-0 max-lg:h-dvh max-lg:max-h-none max-lg:w-full max-lg:max-w-none max-lg:rounded-none max-lg:border-0 max-lg:pt-[env(safe-area-inset-top)] max-lg:overflow-y-auto max-lg:pb-[env(safe-area-inset-bottom)] max-lg:shadow-none"
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
      {/* On a phone the field is drawn as a rounded box of its own, with the cancel
          outside it - the box is the wrapper below, which dissolves from `lg`. */}
      <div className="flex items-center gap-3 border-b border-cv-border px-4 py-3 lg:min-h-16 lg:ps-5 max-lg:sticky max-lg:top-0 max-lg:z-(--cv-z-content-raised) max-lg:gap-2 max-lg:bg-cv-surface max-lg:py-3.5">
        <div className="contents max-lg:flex max-lg:min-h-12 max-lg:min-w-0 max-lg:flex-1 max-lg:items-center max-lg:gap-2 max-lg:rounded-surface max-lg:border-[1.5px] max-lg:border-cv-accent max-lg:px-3">
          <Search
            aria-hidden="true"
            className="size-icon-lg shrink-0 text-cv-accent max-lg:size-icon-md max-lg:text-cv-text-muted"
          />
          <input
            aria-activedescendant={
              activeItem === undefined || results.isPending || results.isError ? undefined : optionId(activeItem)
            }
            aria-autocomplete="list"
            aria-controls={LISTBOX_ID}
            aria-expanded={items.length > 0 && !results.isPending && !results.isError}
            aria-label="חיפוש מועמדות"
            autoComplete="off"
            className="flex-1 bg-transparent text-body font-medium text-cv-text placeholder:text-cv-text-muted focus:ring-0 lg:text-heading-sm lg:font-normal"
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
            <IconButton
              aria-label="ניקוי חיפוש"
              onClick={() => {
                updateSearch("");
                inputRef.current?.focus();
              }}
              size="sm"
              variant="quiet"
            >
              <X aria-hidden="true" className="size-icon-md" />
            </IconButton>
          )}
        </div>
        <Kbd className="hidden text-cv-text-muted lg:inline-block">Esc</Kbd>
        <button className="min-h-11 shrink-0 px-1 font-bold text-cv-text lg:hidden" onClick={onClose} type="button">
          ביטול
        </button>
      </div>

      <div className="max-h-[60vh] overflow-y-auto p-2 max-lg:max-h-none max-lg:shrink-0 max-lg:overflow-visible max-lg:px-3">
        <ResultsStatus results={results} />
        <LiveRegion>{announcement(results)}</LiveRegion>

        <div
          aria-label={results.mode.kind === "attention" ? "דורש טיפול" : "תוצאות חיפוש"}
          className={cx("transition-opacity", isStale && "opacity-60")}
          id={LISTBOX_ID}
          // oxlint-disable-next-line jsx-a11y/prefer-tag-over-role
          role="listbox"
        >
          {results.isError || results.isPending
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
                  key={`${item.kind}:${item.id}`}
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
                  {item.kind === "application" ? (
                    <div className="flex min-w-0 flex-1 items-center gap-3">
                      <ResultKind>מועמדות</ResultKind>
                      <ApplicationSummary item={item.item} />
                    </div>
                  ) : item.kind === "fact" ? (
                    <div className="flex min-w-0 flex-1 items-center gap-3">
                      <ResultKind>עובדה</ResultKind>
                      <span className="min-w-0">
                        <span className="block truncate font-medium text-cv-text">{factLabel(item.fact)}</span>
                        <span className="block truncate text-support text-cv-text-muted">
                          {factStatusLabel(item.fact.status)} · {item.fact.fact_id}
                        </span>
                      </span>
                    </div>
                  ) : (
                    <div className="flex min-w-0 flex-1 items-center gap-3">
                      <ResultKind>היסטוריה</ResultKind>
                      <span className="min-w-0">
                        <span className="block truncate font-medium text-cv-text">
                          {item.event.reason || item.event.event_type}
                        </span>
                        <span className="block truncate text-support text-cv-text-muted">
                          <DateTime format="short" value={item.event.created_at} /> · {item.event.fact_id}
                        </span>
                      </span>
                    </div>
                  )}
                </div>
              ))}
        </div>
      </div>

      {/* "New job" is the list's last row on desktop, as the design draws it under the
          results, and a dashed row in the list's own shape on a phone - an offer, not a
          bar. The footer after it carries the keyboard hints, which fold away on a phone. */}
      <div className="lg:px-3 lg:pb-3 max-lg:px-3 max-lg:pt-1">
        <button
          className="inline-flex items-center gap-1.5 font-medium text-cv-accent hover:underline lg:min-h-11 lg:w-full lg:gap-3 lg:rounded-control lg:px-3 lg:font-bold lg:text-cv-text lg:hover:bg-cv-surface-muted lg:hover:no-underline max-lg:min-h-16 max-lg:w-full max-lg:gap-3 max-lg:rounded-surface max-lg:border max-lg:border-dashed max-lg:border-cv-border-strong max-lg:px-3.5 max-lg:text-body max-lg:font-bold max-lg:text-cv-text max-lg:hover:no-underline"
          onClick={() => {
            onClose();
            void navigate(routePaths.newApplication);
          }}
          type="button"
        >
          <span className="contents max-lg:flex max-lg:size-9 max-lg:items-center max-lg:justify-center max-lg:rounded-control max-lg:bg-cv-accent max-lg:text-cv-on-accent">
            <Plus aria-hidden="true" className="size-icon-sm lg:size-icon-md max-lg:size-icon-md" />
          </span>
          משרה חדשה
        </button>
      </div>

      <div className="flex flex-wrap items-center justify-between gap-2 border-t border-cv-border bg-cv-surface-muted/60 px-4 py-2.5 text-support text-cv-text-muted max-lg:border-t-0 max-lg:bg-transparent max-lg:px-3 max-lg:pt-0 max-lg:pb-4">
        {search.trim() !== "" &&
        !results.isPending &&
        !results.isError &&
        !isStale &&
        results.applicationMatched > shownApplicationCount ? (
          <button
            className="font-medium text-cv-accent hover:underline max-lg:mt-2"
            onClick={() => {
              const params = new URLSearchParams({ activity: "all", search: search.trim() });
              onClose();
              void navigate(`${routePaths.home}?${params.toString()}`);
            }}
            type="button"
          >
            כל {results.applicationMatched} תוצאות המועמדויות
          </button>
        ) : null}

        <div className="hidden items-center gap-2 lg:flex">
          <span>ניווט במקשים:</span>
          <Kbd className="bg-cv-surface px-1 py-0">↑↓</Kbd>
          <span>לבחירה:</span>
          <Kbd className="bg-cv-surface px-1 py-0">↵</Kbd>
        </div>
      </div>
    </dialog>
  );
};

const ResultKind = ({ children }: { children: ReactNode }) => (
  <span className="shrink-0 rounded-control bg-cv-surface-muted px-2 py-1 text-caption font-semibold text-cv-text-muted">
    {children}
  </span>
);

const announcement = ({ isError, isPending, isStale, items }: ApplicationSearch): string | null => {
  if (isError || isPending || isStale) {
    return null;
  }
  return items.length === 0 ? "אין תוצאות" : `${items.length} תוצאות`;
};

const ResultsStatus = ({ results }: { results: ApplicationSearch }) => {
  const { error, isError, isPending, isStale, items, mode, retry } = results;

  if (isError) {
    return (
      <ErrorCallout
        action={
          <Button onClick={retry} variant="secondary">
            ניסיון חוזר
          </Button>
        }
        className="my-6"
        error={error}
        title="החיפוש לא הושלם"
      />
    );
  }

  if (isPending || isStale) {
    return <p className="py-10 text-center text-cv-text-muted">מחפש…</p>;
  }

  /* The listbox's own name says the same for assistive tech, so the visible label is
     hidden from it. Search results are named on desktop only, as its design draws them;
     the phone's list of matches stands without a label. */
  if (items.length > 0) {
    return mode.kind === "attention" ? (
      <p aria-hidden="true" className="px-3 py-1.5 text-support font-semibold text-cv-text-muted">
        דורש טיפול
      </p>
    ) : (
      <p aria-hidden="true" className="hidden px-3 py-1.5 text-support font-semibold text-cv-text-muted lg:block">
        תוצאות חיפוש
      </p>
    );
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
          <p className="font-semibold text-cv-text">אין תוצאות שתואמות ל&quot;{mode.text}&quot;</p>
          <p className="mt-1 text-support text-cv-text-muted">אפשר לנסות מילת חיפוש אחרת או לקלוט משרה חדשה.</p>
        </>
      )}
    </div>
  );
};
