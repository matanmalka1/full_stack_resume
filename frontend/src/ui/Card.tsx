import type { HTMLAttributes, ReactNode } from "react";

import { flatSurfaceClasses } from "./surface";

interface CardProps extends HTMLAttributes<HTMLElement> {
  children: ReactNode;
}

/* A Card is a content boundary, not automatically a floating object. Its default is
   therefore a flat hairline; dialogs, menus and popovers opt into rounded elevation
   through `surfaceClasses` at their own call sites. */
export const Card = ({ children, className, ...rest }: CardProps) => {
  /* `<output>` carries an implicit "status" role, so a status card becomes one instead
     of stamping `role="status"` on a generic section; any other role (e.g. "alert",
     which has no native tag to swap in) keeps the section with its role attribute. */
  if (rest.role === "status") {
    const { role: _role, ...outputRest } = rest;
    return (
      <output className={flatSurfaceClasses(className)} {...outputRest}>
        {children}
      </output>
    );
  }

  return (
    <section className={flatSurfaceClasses(className)} {...rest}>
      {children}
    </section>
  );
};
