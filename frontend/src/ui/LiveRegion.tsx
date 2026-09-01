import type { ReactNode } from "react";

import { cx } from "./cx";

interface LiveRegionProps {
  children?: ReactNode;
  className?: string;
  /* Polite by default. A.5 allows assertive only for a failure the user must notice. */
  tone?: "polite" | "assertive";
  /* Announce without showing; the visible status usually lives in its own component. */
  visuallyHidden?: boolean;
}

/* A.5: autosave, Operation phase, validation completion, and Ready completion announce
   through a live region. Polling ticks pass no children and therefore stay silent. */
export const LiveRegion = ({ children, className, tone = "polite", visuallyHidden = true }: LiveRegionProps) => {
  return (
    <div
      aria-atomic="true"
      aria-live={tone}
      className={cx(visuallyHidden && "sr-only", className)}
      role={tone === "assertive" ? "alert" : "status"}
    >
      {children}
    </div>
  );
};
