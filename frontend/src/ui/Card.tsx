import type { HTMLAttributes, ReactNode } from "react";

import { cardClasses } from "./surface";

interface CardProps extends HTMLAttributes<HTMLElement> {
  children: ReactNode;
}

/* A Card is the design's white, rounded content surface on the grey canvas. Its padding
   is the caller's: a list card runs its rows to the edge, a form card insets them. */
export const Card = ({ children, className, ...rest }: CardProps) => {
  /* `<output>` carries an implicit "status" role, so a status card becomes one instead
     of stamping `role="status"` on a generic section; any other role (e.g. "alert",
     which has no native tag to swap in) keeps the section with its role attribute. */
  if (rest.role === "status") {
    const { role: _role, ...outputRest } = rest;
    return (
      <output className={cardClasses(className)} {...outputRest}>
        {children}
      </output>
    );
  }

  return (
    <section className={cardClasses(className)} {...rest}>
      {children}
    </section>
  );
};
