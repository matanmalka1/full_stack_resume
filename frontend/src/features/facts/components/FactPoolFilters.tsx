import { useId, useState } from "react";
import { ChevronLeft, Clock3, SlidersHorizontal } from "lucide-react";

import type { FactStatus } from "@/api/contracts";
import { cx } from "@/ui/cx";
import { Field } from "@/ui/Field";
import { SearchInput } from "@/ui/Input";
import { Select } from "@/ui/Select";
import type { FactFilters } from "../model/factFilters";
import { factSourceLabel, factStatusLabels } from "../model/factLabels";

interface FactPoolFiltersProps {
  filters: FactFilters;
  onChange: (filters: FactFilters) => void;
  /* How many facts in the whole pool still wait for confirmation, whatever the filters. */
  pendingCount: number;
  sources: string[];
  tags: string[];
}

// Deleted facts are absent from the pool response, so they cannot be filtered here.
const statuses: FactStatus[] = ["pending", "canonical"];

/* A phone has room for one field across, not four. Below the large breakpoint the bar
   keeps the search field (its label read, not drawn), and the knowledge file the pool is
   grouped by becomes a row of chips - the one filter a reader reaches for while
   scrolling. Status and tag are not lost: they fold behind "סינון", whose count says
   when either is set, so a narrowed list never looks like the whole pool.

   The pending banner is the phone's way into the facts that still wait: one tap narrows
   the list to them, a second gives the pool back. On a wide screen the status select
   beside the list already does this, so the banner is not drawn there. */
export const FactPoolFilters = ({ filters, onChange, pendingCount, sources, tags }: FactPoolFiltersProps) => {
  const [moreOpen, setMoreOpen] = useState(false);
  const moreId = useId();
  const moreActive = Number(filters.status !== "all") + Number(filters.tag !== "all");
  const pendingOnly = filters.status === "pending";
  const chips = [
    { label: "הכל", value: "all" },
    ...sources.map((source) => ({ label: factSourceLabel(source), value: source })),
  ];

  return (
    <div className="grid gap-3 max-lg:flex max-lg:flex-col sm:grid-cols-2 xl:grid-cols-4">
      <Field label={<span className="max-lg:sr-only">חיפוש</span>}>
        {(control) => (
          <SearchInput
            {...control}
            onChange={(event) => onChange({ ...filters, query: event.target.value })}
            placeholder="תוכן, מקור או תגית"
            value={filters.query}
          />
        )}
      </Field>

      {pendingCount === 0 ? null : (
        <button
          aria-pressed={pendingOnly}
          className="flex min-h-11 items-center gap-3 rounded-surface bg-cv-accent px-3.5 py-3 text-start text-cv-on-accent shadow-floating lg:hidden"
          onClick={() => onChange({ ...filters, status: pendingOnly ? "all" : "pending" })}
          type="button"
        >
          <span
            aria-hidden="true"
            className="flex size-9 shrink-0 items-center justify-center rounded-control border border-cv-on-accent/30"
          >
            <Clock3 className="size-icon-md" />
          </span>
          <span className="min-w-0 flex-1">
            <span className="block text-body font-bold">
              {pendingCount === 1 ? "עובדה אחת ממתינה לאישורך" : `${pendingCount} עובדות ממתינות לאישורך`}
            </span>
            <span className="block text-support">
              {pendingOnly ? "מוצגות רק הממתינות. נגיעה נוספת מחזירה את כל המאגר." : "רק עובדות מאושרות נכנסות לטיוטות"}
            </span>
          </span>
          <ChevronLeft aria-hidden="true" className="size-icon-md shrink-0" />
        </button>
      )}

      {/* The chips scroll sideways; the toggle stays put at the row's end so the other
          filters are never scrolled out of reach. */}
      <div className="flex items-center gap-2 lg:hidden">
        <div
          aria-label="סינון לפי מאגר מקור"
          className="-my-1 flex min-w-0 flex-1 gap-2 overflow-x-auto py-1"
          // A set of toggles under one name; there is no native grouping element for it.
          // oxlint-disable-next-line jsx-a11y/prefer-tag-over-role
          role="group"
        >
          {chips.map((chip) => {
            const active = filters.source === chip.value;
            return (
              <button
                aria-pressed={active}
                className={cx(
                  "min-h-11 shrink-0 rounded-pill border px-4 text-support font-semibold whitespace-nowrap transition-colors",
                  active
                    ? "border-cv-accent bg-cv-accent text-cv-on-accent"
                    : "border-cv-border bg-cv-surface text-cv-text hover:border-cv-border-strong",
                )}
                key={chip.value}
                onClick={() => onChange({ ...filters, source: chip.value })}
                type="button"
              >
                {chip.label}
              </button>
            );
          })}
        </div>
        <button
          aria-controls={moreId}
          aria-expanded={moreOpen}
          className={cx(
            "inline-flex min-h-11 shrink-0 items-center gap-1.5 rounded-pill border bg-cv-surface px-3.5 text-support font-semibold",
            moreActive > 0 ? "border-cv-accent text-cv-accent" : "border-cv-border text-cv-text",
          )}
          onClick={() => setMoreOpen((open) => !open)}
          type="button"
        >
          <SlidersHorizontal aria-hidden="true" className="size-icon-md" />
          סינון
          {moreActive === 0 ? null : (
            <span className="rounded-pill bg-cv-accent px-1.5 text-caption text-cv-on-accent tabular-nums">
              {moreActive}
              <span className="sr-only"> פעילים</span>
            </span>
          )}
        </button>
      </div>

      {/* `lg:contents` hands the three selects back to the grid on a wide screen, exactly
          where they always stood; below it they are the folded panel. The source select
          stays a wide-screen control - the chips are its phone form. */}
      <div className={cx("flex flex-col gap-3 lg:contents", !moreOpen && "max-lg:hidden")} id={moreId}>
        <Field label="מעמד">
          {(control) => (
            <Select
              {...control}
              onChange={(event) => onChange({ ...filters, status: event.target.value as FactStatus | "all" })}
              value={filters.status}
            >
              <option value="all">כל המעמדות</option>
              {statuses.map((status) => (
                <option key={status} value={status}>
                  {factStatusLabels[status]}
                </option>
              ))}
            </Select>
          )}
        </Field>
        <Field className="max-lg:hidden" label="מאגר מקור">
          {(control) => (
            <Select
              {...control}
              onChange={(event) => onChange({ ...filters, source: event.target.value })}
              value={filters.source}
            >
              <option value="all">כל המאגרים</option>
              {sources.map((source) => (
                <option key={source} value={source}>
                  {factSourceLabel(source)}
                </option>
              ))}
            </Select>
          )}
        </Field>
        <Field label="תגית">
          {(control) => (
            <Select
              {...control}
              onChange={(event) => onChange({ ...filters, tag: event.target.value })}
              value={filters.tag}
            >
              <option value="all">כל התגיות</option>
              {tags.map((tag) => (
                <option key={tag} value={tag}>
                  {tag}
                </option>
              ))}
            </Select>
          )}
        </Field>
      </div>
    </div>
  );
};
