import { useQuery } from "@tanstack/react-query";
import { CircleAlert, Plus, Search, Settings, X } from "lucide-react";
import { type KeyboardEvent, useDeferredValue, useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";

import { applicationListQueryOptions } from "../api/applications";
import type { ApplicationListItem } from "../api/contracts";
import { appRoutes } from "./appRoutes";
import { preparationStateIcons, preparationStateLabels, preparationStateTones } from "../pages/application/applicationLabels";
import { recruitmentStatusLabel, recruitmentStatusTone } from "../pages/application/applicationLabels";
import { StatusBadge } from "../ui/StatusBadge";
import { cx } from "../ui/cx";

interface GlobalSearchDialogProps {
  onClose: () => void;
  open: boolean;
}

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

  /* Empty query: the board's own "needs_attention" preset, so the dialog opens on the
     same answer to "what needs me" the board already gives rather than an arbitrary
     recency slice. Typing replaces that question with the server's free-text search. */
  const query = useQuery(
    applicationListQueryOptions(
      deferredSearch === "" ? { preset: "needs_attention", limit: 8 } : { search: deferredSearch, limit: 8 },
    ),
  );
  const filteredItems = query.data?.items ?? [];

  useEffect(() => {
    setSelectedIndex(0);
  }, [search]);

  useEffect(() => {
    const dialog = dialogRef.current;
    if (dialog === null) {
      return;
    }

    if (open && !dialog.open) {
      dialog.showModal();
      setSearch("");
      setSelectedIndex(0);
      setTimeout(() => inputRef.current?.focus(), 50);
    } else if (!open && dialog.open) {
      dialog.close();
    }
  }, [open]);

  const selectItem = (item: ApplicationListItem) => {
    onClose();
    navigate(appRoutes.application(item.id));
  };

  const handleKeyDown = (e: KeyboardEvent<HTMLInputElement>) => {
    if (e.key === "ArrowDown") {
      e.preventDefault();
      if (filteredItems.length > 0) {
        setSelectedIndex((prev) => (prev + 1) % filteredItems.length);
      }
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      if (filteredItems.length > 0) {
        setSelectedIndex((prev) => (prev - 1 + filteredItems.length) % filteredItems.length);
      }
    } else if (e.key === "Enter") {
      e.preventDefault();
      if (filteredItems.length > 0 && selectedIndex >= 0 && selectedIndex < filteredItems.length) {
        const item = filteredItems[selectedIndex];
        if (item !== undefined) {
          selectItem(item);
        }
      }
    } else if (e.key === "Escape") {
      onClose();
    }
  };

  if (!open) {
    return null;
  }

  return (
    <dialog
      aria-label="חיפוש מהיר של מועמדויות"
      className="fixed left-1/2 top-24 z-50 m-0 flex max-h-[75vh] w-[calc(100%-2rem)] max-w-2xl -translate-x-1/2 flex-col rounded-surface border border-cv-border bg-cv-surface p-0 text-cv-text shadow-floating backdrop:bg-cv-text/40 backdrop:backdrop-blur-sm"
      onClick={(e) => {
        if (e.target === dialogRef.current) {
          onClose();
        }
      }}
      onClose={onClose}
      ref={dialogRef}
    >
      <div className="flex items-center gap-3 border-b border-cv-border px-4 py-3">
        <Search aria-hidden="true" className="size-5 shrink-0 text-cv-accent" />
        <input
          aria-autocomplete="list"
          aria-expanded="true"
          className="flex-1 bg-transparent text-body font-medium text-cv-text placeholder:text-cv-text-muted focus:ring-0"
          dir="auto"
          onChange={(e) => setSearch(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="חברה, תפקיד או מילת מפתח…"
          ref={inputRef}
          role="combobox"
          type="text"
          value={search}
        />
        {search !== "" ? (
          <button
            aria-label="ניקוי חיפוש"
            className="rounded-control p-1 text-cv-text-muted hover:bg-cv-surface-muted hover:text-cv-text"
            onClick={() => {
              setSearch("");
              inputRef.current?.focus();
            }}
            type="button"
          >
            <X aria-hidden="true" className="size-4" />
          </button>
        ) : null}
        <kbd className="hidden rounded border border-cv-border bg-cv-surface-muted px-1.5 py-0.5 text-support font-mono text-cv-text-muted sm:inline-block">
          ESC
        </kbd>
      </div>

      <div className="max-h-[60vh] overflow-y-auto p-2" role="listbox">
        {trimmed === "" && filteredItems.length > 0 ? (
          <p className="px-3 py-1.5 text-support font-semibold text-cv-text-muted">דורש טיפול</p>
        ) : null}

        {filteredItems.length === 0 ? (
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
          filteredItems.map((item, index) => {
            const isSelected = index === selectedIndex;
            const PrepIcon = preparationStateIcons[item.preparation_state];

            return (
              <div
                aria-selected={isSelected}
                className={cx(
                  "flex cursor-pointer items-center justify-between gap-3 rounded-control border p-3 transition-colors",
                  isSelected
                    ? "border-cv-accent/40 bg-cv-accent-soft"
                    : "border-transparent hover:bg-cv-surface-muted",
                )}
                id={`search-result-${item.id}`}
                key={item.id}
                onClick={() => selectItem(item)}
                onMouseEnter={() => setSelectedIndex(index)}
                role="option"
              >
                <div className="flex min-w-0 items-center gap-3">
                  <span
                    aria-hidden="true"
                    className={cx(
                      "flex size-9 shrink-0 items-center justify-center rounded-control text-support font-bold",
                      preparationStateTones[item.preparation_state] === "success"
                        ? "bg-cv-success-soft text-cv-success"
                        : preparationStateTones[item.preparation_state] === "warning"
                          ? "bg-cv-warning-soft text-cv-warning"
                          : "bg-cv-surface-muted text-cv-accent",
                    )}
                  >
                    {[...item.company][0] ?? "?"}
                  </span>
                  <div className="min-w-0">
                    <p className="truncate font-semibold text-cv-text" dir="auto">
                      {item.company}
                    </p>
                    <p className="truncate text-support text-cv-text-muted" dir="auto">
                      {item.target_role}
                    </p>
                  </div>
                </div>

                <div className="flex shrink-0 items-center gap-2">
                  <StatusBadge
                    className="px-2 py-0.5 text-xs"
                    icon={PrepIcon}
                    tone={preparationStateTones[item.preparation_state]}
                  >
                    {preparationStateLabels[item.preparation_state]}
                  </StatusBadge>
                  <StatusBadge
                    className="px-2 py-0.5 text-xs"
                    tone={recruitmentStatusTone(item.current_status)}
                  >
                    {recruitmentStatusLabel(item.current_status)}
                  </StatusBadge>
                </div>
              </div>
            );
          })
        )}
      </div>

      <div className="flex flex-wrap items-center justify-between gap-2 border-t border-cv-border bg-cv-surface-muted/60 px-4 py-2.5 text-support text-cv-text-muted">
        <div className="flex items-center gap-3">
          <button
            className="inline-flex items-center gap-1.5 font-medium text-cv-accent hover:underline"
            onClick={() => {
              onClose();
              navigate(appRoutes.newApplication);
            }}
            type="button"
          >
            <Plus aria-hidden="true" className="size-3.5" />
            משרה חדשה
          </button>
          <span>·</span>
          <button
            className="inline-flex items-center gap-1.5 hover:text-cv-text hover:underline"
            onClick={() => {
              onClose();
              navigate(appRoutes.settings);
            }}
            type="button"
          >
            <Settings aria-hidden="true" className="size-3.5" />
          </button>
        </div>

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
