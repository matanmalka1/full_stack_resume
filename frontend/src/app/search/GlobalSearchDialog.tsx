import { BookOpen, CircleAlert, CircleX, Clock, CornerDownLeft, Plus, Search } from "lucide-react";
import { type KeyboardEvent, type ReactNode, useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";

import { ApplicationSummary } from "@/features/application-list";
import { factLabel } from "@/features/facts";
import { preparationResumeDestination } from "@/features/preparation";
import { ErrorCallout } from "@/ui/ErrorCallout";
import { Button } from "@/ui/Button";
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

/* The part of a result that matched the field, marked the way the design draws it: a grey
   wash behind the matched letters, the text itself unchanged. Case is ignored, as the
   search itself ignores it. */
const marker =
  (needle: string) =>
  (text: string): ReactNode => {
    const at = needle === "" ? -1 : text.toLocaleLowerCase().indexOf(needle.toLocaleLowerCase());
    if (at === -1) return text;
    return (
      <>
        {text.slice(0, at)}
        <mark className="rounded-sm bg-cv-border text-inherit">{text.slice(at, at + needle.length)}</mark>
        {text.slice(at + needle.length)}
      </>
    );
  };

/* Results come in the design's two groups: what matched - Applications and facts - and the
   history of those facts. An empty field asks what waits on the reader instead. */
const sections = (results: ApplicationSearch): { id: string; items: readonly GlobalSearchItem[]; title: string }[] => {
  const matches = results.items.filter((item) => item.kind !== "history");
  const history = results.items.filter((item) => item.kind === "history");
  return [
    { id: "matches", items: matches, title: results.mode.kind === "attention" ? "דורש טיפול" : "תוצאות חיפוש" },
    { id: "history", items: history, title: "היסטוריה" },
  ].filter((section) => section.items.length > 0);
};

/* Command palette: find an Application or a fact and go to it. Uses native <dialog>
   directly (not `ui/Dialog`) because its whole surface is one combobox that owns focus.

   On a wide screen it is a card over the dimmed app, its field the card's top edge. Below
   the large breakpoint it is the whole screen, as a phone's own search is: the field boxed
   at the top with a cancel beside it, then the results and the new-job row after them,
   scrolling as one column. */
export const GlobalSearchDialog = ({ onClose, open }: GlobalSearchDialogProps) => {
  const navigate = useNavigate();
  const dialogRef = useRef<HTMLDialogElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const [activeIndex, setActiveIndex] = useState(0);
  const results = useApplicationSearch(open);
  const { isStale, search, setSearch } = results;
  const grouped = sections(results);
  /* Keyboard order is the drawn order, group after group. */
  const items = grouped.flatMap((section) => section.items);
  const mark = marker(results.mode.kind === "search" ? results.mode.text : "");

  // Clamped: a new result set may be shorter than the one the index was chosen in.
  const active = Math.min(activeIndex, items.length - 1);
  const activeItem = active >= 0 ? items[active] : undefined;
  const showRows = !results.isError && !results.isPending;

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
    if (items.length === 0 || !showRows || isStale || event.nativeEvent.isComposing) {
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

  const option = (item: GlobalSearchItem) => {
    const index = items.indexOf(item);
    const selected = index === active;
    const history = item.kind === "history";

    return (
      // Keyboard selection is owned by the combobox; options never take focus.
      // oxlint-disable-next-line jsx-a11y/click-events-have-key-events
      <div
        aria-selected={selected}
        className={cx(
          "flex cursor-pointer items-center gap-3 rounded-control px-1 transition-colors lg:px-3",
          history ? "min-h-12 lg:min-h-11" : "min-h-14 py-2.5",
          selected ? "lg:bg-cv-canvas" : undefined,
          !history && "max-lg:border-t max-lg:border-cv-canvas max-lg:rounded-none max-lg:first:border-t-0",
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
          <ApplicationSummary item={item.item} mark={mark} />
        ) : item.kind === "fact" ? (
          <>
            <span
              aria-hidden="true"
              className="flex size-10 shrink-0 items-center justify-center rounded-control bg-cv-canvas text-cv-accent lg:size-9 lg:rounded-control-sm"
            >
              <BookOpen className="size-icon-md" />
            </span>
            <span className="min-w-0 flex-1">
              <span className="block truncate text-body font-bold text-cv-text">{mark(factLabel(item.fact))}</span>
              <span className="block truncate text-support text-cv-text-muted">עובדה</span>
            </span>
          </>
        ) : (
          <>
            <Clock aria-hidden="true" className="size-4.5 shrink-0 text-cv-text-muted lg:size-icon-md" />
            <span className="min-w-0 flex-1 truncate text-body text-cv-text lg:text-label">
              {mark(item.event.reason || item.event.event_type)} ·{" "}
              <span className="text-cv-text-muted">
                <DateTime format="short" value={item.event.created_at} />
              </span>
            </span>
          </>
        )}
        {/* What Enter does, beside the row it would open. */}
        {selected ? (
          <CornerDownLeft aria-hidden="true" className="size-icon-sm shrink-0 text-cv-text-muted max-lg:hidden" />
        ) : null}
      </div>
    );
  };

  return (
    <dialog
      // `open:flex` only: an unconditional `flex` would override the closed dialog's `display: none`.
      // Centred by `inset-x-0 mx-auto`: with a fixed width in RTL, `left` loses to the UA's `right: 0`.
      aria-label="מעבר מהיר למועמדות"
      className="fixed inset-x-0 top-24 bottom-auto mx-auto my-0 hidden max-h-[75vh] w-[calc(100%-2rem)] max-w-170 flex-col overflow-hidden rounded-dialog border-0 bg-cv-surface p-0 text-cv-text shadow-overlay open:flex backdrop:bg-cv-scrim max-lg:inset-0 max-lg:h-dvh max-lg:max-h-none max-lg:w-full max-lg:max-w-none max-lg:overflow-y-auto max-lg:rounded-none max-lg:pt-[env(safe-area-inset-top)] max-lg:pb-[env(safe-area-inset-bottom)] max-lg:shadow-none"
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
      <div className="flex shrink-0 items-center gap-3 border-b border-cv-hairline px-5.5 max-lg:sticky max-lg:top-0 max-lg:z-(--cv-z-content-raised) max-lg:gap-2 max-lg:bg-cv-surface max-lg:px-4 max-lg:pt-3.5 max-lg:pb-3">
        <div className="contents max-lg:flex max-lg:h-12 max-lg:min-w-0 max-lg:flex-1 max-lg:items-center max-lg:gap-2 max-lg:rounded-control-lg max-lg:border-[1.5px] max-lg:border-cv-accent max-lg:bg-cv-field-background max-lg:ps-3.5 max-lg:pe-0.5">
          <Search aria-hidden="true" className="size-icon-lg shrink-0 text-cv-text-muted max-lg:size-4.5" />
          <input
            aria-activedescendant={activeItem === undefined || !showRows ? undefined : optionId(activeItem)}
            aria-autocomplete="list"
            aria-controls={LISTBOX_ID}
            aria-expanded={items.length > 0 && showRows}
            aria-label="חיפוש מועמדות"
            autoComplete="off"
            className="h-16 min-w-0 flex-1 bg-transparent text-heading-sm text-cv-text placeholder:text-cv-text-muted focus:ring-0 max-lg:h-11 max-lg:text-field"
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
              className="flex size-10 shrink-0 items-center justify-center rounded-control-sm text-cv-text-muted hover:text-cv-text max-lg:size-11"
              onClick={() => {
                updateSearch("");
                inputRef.current?.focus();
              }}
              type="button"
            >
              <CircleX aria-hidden="true" className="size-4.5" />
            </button>
          )}
        </div>
        <kbd
          className="hidden shrink-0 rounded-item border border-cv-border px-2 py-0.5 font-sans text-caption text-cv-text-muted lg:inline-block"
          dir="ltr"
        >
          Esc
        </kbd>
        <button
          className="min-h-11 shrink-0 px-1 text-body font-bold text-cv-text lg:hidden"
          onClick={onClose}
          type="button"
        >
          ביטול
        </button>
      </div>

      <div className="flex min-h-0 flex-col gap-2.5 overflow-y-auto p-3 max-lg:shrink-0 max-lg:gap-5 max-lg:overflow-visible max-lg:p-4">
        <ResultsStatus results={results} />
        <LiveRegion>{announcement(results)}</LiveRegion>

        <div
          aria-label={results.mode.kind === "attention" ? "דורש טיפול" : "תוצאות חיפוש"}
          className={cx("flex flex-col gap-2.5 transition-opacity max-lg:gap-5", isStale && "opacity-60")}
          id={LISTBOX_ID}
          // oxlint-disable-next-line jsx-a11y/prefer-tag-over-role
          role="listbox"
        >
          {showRows
            ? grouped.map((section) => (
                <div
                  aria-labelledby={`global-search-${section.id}`}
                  className="flex flex-col gap-1.5"
                  key={section.id}
                  // A group of options inside the listbox; no native tag is allowed there.
                  // oxlint-disable-next-line jsx-a11y/prefer-tag-over-role
                  role="group"
                >
                  <p
                    className="mx-1 mt-1 text-caption font-bold text-cv-text-muted lg:mx-2 max-lg:text-support"
                    id={`global-search-${section.id}`}
                  >
                    {section.title}
                  </p>
                  <div>{section.items.map(option)}</div>
                </div>
              ))
            : null}
        </div>

        {/* A new job is an offer beside the results, not one of them: a row in the list's
            own shape on a wide screen, a dashed box at the end of the column on a phone. */}
        <button
          className="flex min-h-11 items-center gap-3 rounded-control px-3 text-start text-label font-bold text-cv-text hover:bg-cv-canvas max-lg:min-h-15 max-lg:rounded-control-lg max-lg:border max-lg:border-dashed max-lg:border-cv-border-strong max-lg:px-3.5 max-lg:text-body"
          onClick={() => {
            onClose();
            void navigate(routePaths.newApplication);
          }}
          type="button"
        >
          <span className="contents max-lg:flex max-lg:size-9 max-lg:shrink-0 max-lg:items-center max-lg:justify-center max-lg:rounded-control-sm max-lg:bg-cv-accent max-lg:text-cv-on-accent">
            <Plus aria-hidden="true" className="size-icon-md" />
          </span>
          קליטת משרה חדשה
        </button>
      </div>

      <div className="flex shrink-0 items-center gap-4 border-t border-cv-hairline bg-cv-field-background px-5 py-2.5 text-caption text-cv-text-muted max-lg:hidden">
        <span>
          ניווט במקשים: <kbd dir="ltr">↑↓</kbd>
        </span>
        <span>
          לבחירה: <kbd dir="ltr">↵</kbd>
        </span>
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

  if (items.length > 0) {
    return null;
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
