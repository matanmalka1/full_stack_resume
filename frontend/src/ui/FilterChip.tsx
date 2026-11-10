import type { ButtonHTMLAttributes, ReactNode } from "react";

import { type ClassValue, cx } from "./cx";

/* How a chip's count draws. "plain" is a bold number beside the label; "badge" is the
   same number in a filled disc, for the one slice that waits on the reader. */
type FilterChipCount = "plain" | "badge";

/* The pill a quick filter draws, as class data so a router Link that changes the URL's
   filter can carry it as well as the toggle button below. Pressed, it fills with the
   accent; a chip that asks for attention keeps a stronger edge at rest. */
const filterChipClasses = (pressed: boolean, emphasis = false, className?: ClassValue): string =>
  cx(
    "inline-flex h-9.5 shrink-0 items-center gap-1.5 rounded-pill border text-label whitespace-nowrap transition-colors max-lg:h-8",
    pressed
      ? "border-cv-accent bg-cv-accent px-4 font-bold text-cv-on-accent max-lg:px-3.5"
      : cx(
          "bg-cv-surface px-3.5 hover:border-cv-border-strong max-lg:px-3",
          emphasis
            ? "border-cv-border-strong font-bold text-cv-text"
            : "border-cv-border font-medium text-cv-text-muted",
        ),
    className,
  );

/* The number beside a chip's label. Decorative styling only - the number is real text
   and is read as part of the chip's name. */
const FilterChipCountMark = ({
  count,
  pressed,
  variant = "plain",
}: {
  count: number;
  pressed: boolean;
  variant?: FilterChipCount;
}) =>
  variant === "badge" && !pressed ? (
    <span className="inline-flex h-5.5 min-w-5.5 items-center justify-center rounded-pill bg-cv-text px-1.5 text-caption font-bold text-cv-surface">
      {count}
    </span>
  ) : (
    <span className={pressed ? "font-medium opacity-80" : "font-bold text-cv-text"}>{count}</span>
  );

interface FilterChipProps extends Omit<ButtonHTMLAttributes<HTMLButtonElement>, "children"> {
  children: ReactNode;
  count?: number;
  countVariant?: FilterChipCount;
  pressed: boolean;
}

/* One quick filter in a row of them - the board's presets, the fact pool's kinds. A toggle
   button: `aria-pressed` says which slice is shown, and the row around it is a labelled
   group the caller draws. */
export const FilterChip = ({
  children,
  className,
  count,
  countVariant = "plain",
  pressed,
  type = "button",
  ...rest
}: FilterChipProps) => (
  <button
    aria-pressed={pressed}
    className={filterChipClasses(pressed, countVariant === "badge", className)}
    type={type}
    {...rest}
  >
    {children}
    {/* The space keeps the label and its count two words in the chip's name. */}
    {count === undefined ? null : (
      <>
        {" "}
        <FilterChipCountMark count={count} pressed={pressed} variant={countVariant} />
      </>
    )}
  </button>
);
