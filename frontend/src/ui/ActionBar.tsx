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
        "mt-8 flex flex-wrap items-center justify-between gap-3 border-t border-cv-border pt-6",
        className,
      )}
    >
      <div className="flex flex-wrap gap-3">{secondary}</div>
      <div className="flex flex-wrap gap-3">{primary}</div>
    </div>
  );
};
