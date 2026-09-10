import type { HTMLAttributes, ReactNode } from "react";

import { surfaceClasses } from "./surface";

interface CardProps extends HTMLAttributes<HTMLElement> {
  children: ReactNode;
}

/* Shared radius+border pairing for every bordered surface. Background, shadow, and
   padding vary per call site (muted/raised bg, inner/document/floating shadow, custom
   padding) and are supplied via className rather than baked in, since this project's
   `cx` is a plain concat with no conflict resolution: a default here would collide
   unpredictably with a caller's override. */
export const Card = ({ children, className, ...rest }: CardProps) => {
  /* `<output>` carries an implicit "status" role, so a status card becomes one instead
     of stamping `role="status"` on a generic section; any other role (e.g. "alert",
     which has no native tag to swap in) keeps the section with its role attribute. */
  if (rest.role === "status") {
    const { role: _role, ...outputRest } = rest;
    return (
      <output className={surfaceClasses(className)} {...outputRest}>
        {children}
      </output>
    );
  }

  return (
    <section className={surfaceClasses(className)} {...rest}>
      {children}
    </section>
  );
};
