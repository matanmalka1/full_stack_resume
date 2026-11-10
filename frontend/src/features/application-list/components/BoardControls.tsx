import { ChevronDown } from "lucide-react";

import type { ApplicationSort } from "@/api/contracts";
import { cx } from "@/ui/cx";

/* Exhaustive over the generated union, so an order added to the list endpoint fails the
   build here rather than being missing from the menu. Each order has one direction on
   the server, and the label says which. */
const sortLabels: Record<ApplicationSort, string> = {
  updated: "עודכן לאחרונה",
  created: "נוצר לאחרונה",
  company: "שם החברה",
  stage: "התקדמות ההכנה",
};

const sortOrder = Object.keys(sortLabels) as ApplicationSort[];

/* The order, drawn as the design's quiet "מיון: עודכן לאחרונה ▾" control and backed by a
   native select laid over it: the platform's own menu on every device, the keyboard and a
   screen reader get a real listbox, and the drawn text is only what the select shows.
   "plain" is the phone's bare text in the cards' header; "boxed" the wide screen's
   bordered control beside the title. */
export const BoardSort = ({
  onChange,
  value,
  variant,
}: {
  onChange: (sort: ApplicationSort) => void;
  value: ApplicationSort;
  variant: "plain" | "boxed";
}) => (
  <label
    className={cx(
      "relative inline-flex shrink-0 items-center gap-1.5 text-support has-[:focus-visible]:outline-2 has-[:focus-visible]:outline-offset-2 has-[:focus-visible]:outline-cv-focus",
      variant === "boxed"
        ? "h-10 rounded-control-sm border border-cv-border bg-cv-surface px-3 text-cv-text"
        : "min-h-8 rounded-item text-cv-text-muted",
    )}
  >
    <span aria-hidden="true">
      {variant === "boxed" ? "מיון: " : null}
      {sortLabels[value]}
    </span>
    <ChevronDown aria-hidden="true" className="size-icon-sm" />
    <select
      aria-label="מיון"
      className="absolute inset-0 cursor-pointer opacity-0"
      name="sort"
      onChange={(event) => onChange(event.target.value as ApplicationSort)}
      value={value}
    >
      {sortOrder.map((sort) => (
        <option key={sort} value={sort}>
          {sortLabels[sort]}
        </option>
      ))}
    </select>
  </label>
);
