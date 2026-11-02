import type { HTMLAttributes, ReactNode } from "react";

import { cx } from "./cx";

interface EmptyStateProps extends HTMLAttributes<HTMLDivElement> {
  children: ReactNode;
}

/* The design's empty frame: a dashed outline on the canvas, with no surface of its own,
   so it reads as room the work will fill rather than as a card that holds nothing. */
export const EmptyState = ({ children, className, ...rest }: EmptyStateProps) => (
  <div
    className={cx("rounded-sheet border-[1.5px] border-dashed border-cv-border-soft px-6 py-10 text-center", className)}
    {...rest}
  >
    {children}
  </div>
);
