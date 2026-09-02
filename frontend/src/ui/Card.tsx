import type { HTMLAttributes, ReactNode } from "react";

import { surfaceClasses } from "./Surface";

interface CardProps extends HTMLAttributes<HTMLElement> {
  children: ReactNode;
}

/* Shared radius+border pairing for every bordered surface. Background, shadow, and
   padding vary per call site (muted/raised bg, inner/document/floating shadow, custom
   padding) and are supplied via className rather than baked in, since this project's
   `cx` is a plain concat with no conflict resolution: a default here would collide
   unpredictably with a caller's override. */
export const Card = ({ children, className, ...rest }: CardProps) => {
  return (
    <section className={surfaceClasses(className)} {...rest}>
      {children}
    </section>
  );
};
