import { ChevronLeft, CircleCheck } from "lucide-react";
import type { ReactNode } from "react";
import { Link } from "react-router-dom";

import { cx } from "@/ui/cx";
import { FilterChip } from "@/ui/FilterChip";
import { SearchInput } from "@/ui/Input";
import type { FactFilters } from "../model/factFilters";
import { factSourceLabel } from "../model/factLabels";

interface FactPoolFiltersProps {
  filters: FactFilters;
  onChange: (filters: FactFilters) => void;
  /* Where the banner leads when exactly one fact waits: straight to it. */
  pendingHref: string | null;
  /* How many facts in the whole pool still wait for confirmation, whatever the filters. */
  pendingCount: number;
  /* The knowledge files the pool holds, each with how many facts it has. */
  sources: { count: number; source: string }[];
  total: number;
}

const bannerClasses =
  "flex min-h-11 items-center gap-3 rounded-surface bg-cv-accent px-3.5 py-3 text-start text-cv-on-accent shadow-floating lg:px-4.5 lg:py-3.5 lg:shadow-none";

/* The dark strip that says how many facts wait for the reader. With one waiting it is a
   link to that fact, as the design draws it; with several, opening one would leave the
   rest unnamed, so the strip narrows the pool to them instead and a second press gives
   the whole pool back. */
const PendingBanner = ({
  count,
  href,
  onToggle,
  pressed,
}: {
  count: number;
  href: string | null;
  onToggle: () => void;
  pressed: boolean;
}) => {
  const content = (trailing: ReactNode, detail: ReactNode) => (
    <>
      <span
        aria-hidden="true"
        className="flex size-9 shrink-0 items-center justify-center rounded-control-sm bg-cv-on-accent/15 lg:size-auto lg:bg-transparent"
      >
        <CircleCheck className="size-icon-md lg:size-icon-lg" />
      </span>
      <span className="min-w-0 flex-1">
        <span className="block text-body font-bold">
          {count === 1 ? "עובדה אחת ממתינה לאישורך" : `${count} עובדות ממתינות לאישורך`}
        </span>
        <span className="block text-support opacity-85 lg:hidden">{detail}</span>
      </span>
      <span className="text-support font-bold underline max-lg:hidden">{trailing}</span>
      <ChevronLeft aria-hidden="true" className="size-icon-md shrink-0 lg:hidden" />
    </>
  );

  if (href !== null) {
    return (
      <Link className={bannerClasses} to={href}>
        {content("לבדיקה", "רק עובדות מאושרות נכנסות לטיוטות")}
      </Link>
    );
  }

  return (
    <button aria-pressed={pressed} className={bannerClasses} onClick={onToggle} type="button">
      {pressed
        ? content("הצגת כל המאגר", "מוצגות רק הממתינות. נגיעה נוספת מחזירה את כל המאגר.")
        : content("הצגת הממתינות", "רק עובדות מאושרות נכנסות לטיוטות")}
    </button>
  );
};

/* The pool's three ways in, in the design's order for each width: a phone stacks the
   search field, the pending banner and a sideways-scrolling row of chips; a wide screen
   leads with the banner and sets the field and the chips side by side under it. The
   chips are the knowledge files the pool holds - the one axis every fact has exactly one
   of, and the one the phone's list is grouped by. */
export const FactPoolFilters = ({
  filters,
  onChange,
  pendingCount,
  pendingHref,
  sources,
  total,
}: FactPoolFiltersProps) => {
  const chips = [
    { count: total, label: "הכל", value: "all" },
    ...sources.map(({ count, source }) => ({ count, label: factSourceLabel(source), value: source })),
  ];

  return (
    <div className="flex flex-col gap-3.5 lg:flex-row lg:flex-wrap lg:items-center lg:gap-3">
      <div className="min-w-0 lg:flex-1 lg:basis-70">
        <label className="sr-only" htmlFor="fact-search">
          חיפוש עובדות
        </label>
        <SearchInput
          className="shadow-surface lg:shadow-none"
          id="fact-search"
          onChange={(event) => onChange({ ...filters, query: event.target.value })}
          placeholder="חיפוש עובדה, מיומנות או תפקיד"
          value={filters.query}
        />
      </div>

      {pendingCount === 0 ? null : (
        <div className="flex flex-col lg:order-first lg:basis-full">
          <PendingBanner
            count={pendingCount}
            href={pendingHref}
            onToggle={() => onChange({ ...filters, pendingOnly: !filters.pendingOnly })}
            pressed={filters.pendingOnly}
          />
        </div>
      )}

      {/* A phone's row runs to the screen's edges and scrolls sideways; a wide screen has
          room to wrap it beside the field. */}
      <div
        aria-label="סינון לפי מאגר מקור"
        className={cx(
          "flex gap-2",
          "cv-scroll-quiet max-lg:-mx-4 max-lg:overflow-x-auto max-lg:px-4 max-lg:py-0.5",
          "lg:flex-wrap",
        )}
        // A set of toggles under one name; there is no native grouping element for it.
        // oxlint-disable-next-line jsx-a11y/prefer-tag-over-role
        role="group"
      >
        {chips.map((chip) => (
          <FilterChip
            count={chip.count}
            key={chip.value}
            onClick={() => onChange({ ...filters, source: chip.value })}
            pressed={filters.source === chip.value}
          >
            {chip.label}
          </FilterChip>
        ))}
      </div>
    </div>
  );
};
