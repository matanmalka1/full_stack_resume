import type { HTMLAttributes, ReactNode } from "react";

import { flatSurfaceClasses, raisedSurfaceClasses } from "./surface";

interface CardProps extends HTMLAttributes<HTMLElement> {
  children: ReactNode;
  /* "flat" (the default) is a hairline region. "raised" is the desktop design's content
     card - white, rounded, a faint shadow - at every width; "wide-raised" is raised from
     the large breakpoint and flat below it, so a screen can adopt the desktop card without
     moving its phone layout. */
  variant?: "flat" | "raised" | "wide-raised";
}

const cardClasses = (variant: CardProps["variant"], className?: string): string => {
  if (variant === "raised") {
    return raisedSurfaceClasses(className);
  }
  if (variant === "wide-raised") {
    return raisedSurfaceClasses(className, "wide");
  }
  return flatSurfaceClasses(className);
};

/* A Card is a content boundary, not automatically a floating object. Its default is
   therefore a flat hairline; dialogs, menus and popovers opt into rounded elevation
   through `surfaceClasses` at their own call sites, and a content panel on the canvas opts
   into the design's card through `variant`. */
export const Card = ({ children, className, variant = "flat", ...rest }: CardProps) => {
  /* `<output>` carries an implicit "status" role, so a status card becomes one instead
     of stamping `role="status"` on a generic section; any other role (e.g. "alert",
     which has no native tag to swap in) keeps the section with its role attribute. */
  if (rest.role === "status") {
    const { role: _role, ...outputRest } = rest;
    return (
      <output className={cardClasses(variant, className)} {...outputRest}>
        {children}
      </output>
    );
  }

  return (
    <section className={cardClasses(variant, className)} {...rest}>
      {children}
    </section>
  );
};
