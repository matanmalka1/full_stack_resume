import type { HTMLAttributes, ReactNode } from "react";

import { cx } from "./cx";

interface EmptyStateProps extends HTMLAttributes<HTMLDivElement> {
  children: ReactNode;
}

export const EmptyState = ({ children, className, ...rest }: EmptyStateProps) => (
  <div
    className={cx(
      "rounded-surface border border-dashed border-cv-border p-8 text-center",
      className,
    )}
    {...rest}
  >
    {children}
  </div>
);
