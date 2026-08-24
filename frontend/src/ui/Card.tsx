import type { HTMLAttributes, ReactNode } from "react";

import { cx } from "./cx";

interface CardProps extends HTMLAttributes<HTMLElement> {
  children: ReactNode;
}

/* The single surface level of A.2: white surface, one border, no shadow. */
export const Card = ({ children, className, ...rest }: CardProps) => {
  return (
    <section
      className={cx("rounded-surface border border-cv-border bg-cv-surface p-8", className)}
      {...rest}
    >
      {children}
    </section>
  );
};
