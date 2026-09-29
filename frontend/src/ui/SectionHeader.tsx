import type { LucideIcon } from "lucide-react";
import type { ReactNode } from "react";

import { cx } from "./cx";

interface SectionHeaderProps {
  actions?: ReactNode;
  align?: "start" | "center" | "baseline";
  className?: string;
  description?: ReactNode;
  gap?: "standard" | "wide" | "wide-compact";
  headingId?: string;
  headingSize?: "section" | "body";
  icon?: LucideIcon;
  spacing?: "compact" | "roomy";
  title: ReactNode;
}

const alignmentClasses: Record<NonNullable<SectionHeaderProps["align"]>, string> = {
  start: "items-start",
  center: "items-center",
  baseline: "items-baseline",
};

const gapClasses: Record<NonNullable<SectionHeaderProps["gap"]>, string> = {
  standard: "gap-3",
  wide: "gap-x-6 gap-y-3",
  "wide-compact": "gap-x-6 gap-y-2",
};

/* A section masthead has one stable reading order: title and explanation first, then
   its local status or action. */
export const SectionHeader = ({
  actions,
  align = "start",
  className,
  description,
  gap = "standard",
  headingId,
  headingSize = "section",
  icon: Icon,
  spacing = "compact",
  title,
}: SectionHeaderProps) => {
  const text = (
    <div className="min-w-0">
      <h2
        className={
          headingSize === "section" ? "text-heading-sm font-bold text-cv-text" : "text-body font-semibold text-cv-text"
        }
        id={headingId}
      >
        {title}
      </h2>
      {description === undefined ? null : <p className="mt-1 text-support text-cv-text-muted">{description}</p>}
    </div>
  );

  return (
    <div
      className={cx(
        "flex flex-wrap justify-between border-b border-cv-border",
        alignmentClasses[align],
        gapClasses[gap],
        spacing === "roomy" ? "pb-4" : "pb-3",
        className,
      )}
    >
      {Icon === undefined ? (
        text
      ) : (
        <div className="flex min-w-0 items-start gap-2.5">
          <span className="flex size-9 shrink-0 items-center justify-center rounded-control bg-cv-accent-soft text-cv-accent">
            <Icon aria-hidden="true" className="size-icon-md" />
          </span>
          {text}
        </div>
      )}
      {actions === undefined ? null : actions}
    </div>
  );
};
