import type { HTMLAttributes, ReactNode } from "react";

import { cx } from "./cx";

interface CardProps extends HTMLAttributes<HTMLElement> {
  children: ReactNode;
}

/* The primary workspace surface. Its low elevation separates work from the canvas
   without turning every nested region into another floating card. */
export const Card = ({ children, className, ...rest }: CardProps) => {
  return (
    <section
      className={cx(
        "rounded-surface border border-cv-border bg-cv-surface p-5 shadow-surface sm:p-8",
        className,
      )}
      {...rest}
    >
      {children}
    </section>
  );
};
