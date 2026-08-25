import type { ReactNode } from "react";

import { cx } from "./cx";

interface ActionBarProps {
  className?: string;
  /* A.1: one emphasized primary action per page. */
  primary: ReactNode;
  secondary?: ReactNode;
}

export const ActionBar = ({ className, primary, secondary }: ActionBarProps) => {
  return (
    <div
      className={cx(
        "mt-8 flex flex-wrap items-center gap-3 rounded-surface border border-cv-border bg-cv-surface-muted p-4 shadow-inner",
        /* With no secondary actions the bar has one side, so the primary takes the end
           rather than being pushed there by an empty container. */
        secondary === undefined ? "justify-end" : "justify-between",
        className,
      )}
    >
      {secondary === undefined ? null : <div className="flex flex-wrap gap-3">{secondary}</div>}
      <div className="flex flex-wrap gap-3">{primary}</div>
    </div>
  );
};
