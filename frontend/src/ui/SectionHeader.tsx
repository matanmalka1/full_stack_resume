import type { LucideIcon } from "lucide-react";
import { createElement, type ReactNode } from "react";

import { cx } from "./cx";

type HeadingLevel = "h2" | "h3" | "h4";

interface SectionHeaderProps {
  actions?: ReactNode;
  align?: "start" | "center" | "baseline";
  className?: string;
  constrainDescription?: boolean;
  description?: ReactNode;
  gap?: "standard" | "tight" | "wide" | "wide-compact";
  headingId?: string;
  headingLevel?: HeadingLevel;
  headingSize?: "section" | "body";
  icon?: LucideIcon;
  iconPresentation?: "badge" | "inline";
  leadingDescription?: boolean;
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
  tight: "gap-2",
  wide: "gap-x-6 gap-y-3",
  "wide-compact": "gap-x-6 gap-y-2",
};

/* A section masthead has one stable reading order: title and explanation first, then
   its local status or action. Callers still choose the heading level and icon treatment
   because those carry document hierarchy and visual emphasis, not boilerplate. */
export const SectionHeader = ({
  actions,
  align = "start",
  className,
  constrainDescription = false,
  description,
  gap = "standard",
  headingId,
  headingLevel = "h2",
  headingSize = "section",
  icon: Icon,
  iconPresentation = "badge",
  leadingDescription = false,
  spacing = "compact",
  title,
}: SectionHeaderProps) => {
  const heading = createElement(
    headingLevel,
    {
      className:
        headingSize === "section"
          ? "text-heading-sm font-bold text-cv-text"
          : "text-body font-semibold text-cv-text",
      id: headingId,
    },
    title,
  );
  const text = (
    <div className="min-w-0">
      {heading}
      {description === undefined ? null : (
        <p
          className={cx(
            "mt-1 text-support text-cv-text-muted",
            constrainDescription ? "max-w-2xl" : undefined,
            leadingDescription ? "leading-6" : undefined,
          )}
        >
          {description}
        </p>
      )}
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
      ) : iconPresentation === "badge" ? (
        <div className="flex min-w-0 items-start gap-2.5">
          <span className="flex size-9 shrink-0 items-center justify-center rounded-control bg-cv-accent-soft text-cv-accent">
            <Icon aria-hidden="true" className="size-4" />
          </span>
          {text}
        </div>
      ) : (
        <div className="flex min-w-0 items-center gap-2">
          <Icon aria-hidden="true" className="size-4 shrink-0 text-cv-accent" />
          {text}
        </div>
      )}
      {actions === undefined ? null : actions}
    </div>
  );
};
