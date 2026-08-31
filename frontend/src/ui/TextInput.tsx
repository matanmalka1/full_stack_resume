import type { ComponentProps } from "react";

import { cx } from "./cx";

/* ComponentProps rather than the attribute types alone: these carry `ref`, which is
   how React Hook Form binds an uncontrolled field to the primitive. */

/* The resting edge is the plain border token, matching cards and separators, so a
   form reads as one surface rather than a stack of hard boxes. Weight comes from an
   inset hairline in the same cool neutral as the shadow tokens, not Tailwind's black
   `shadow-inner`. Hover darkens the edge to the muted text value - a real step up
   from the resting border, which the previous strong-border pairing was not, since
   both hexes were identical. Focus drops the inset and offsets the accent ring so
   ring and border stay legible instead of blurring into one thick edge. Invalid
   carries its own ring at rest rather than only once focused.

   Height stays at the call sites: `cx` is a plain join with no conflict resolution,
   so a `min-h` here would collide with the textarea's own. */
export const controlClasses =
  "block w-full rounded-control border border-cv-border bg-cv-surface px-3.5 py-2.5 text-body text-cv-text shadow-[inset_0_1px_2px_rgb(17_24_39_/_0.04)] transition-[border-color,box-shadow,background-color] duration-200 placeholder:text-cv-text-muted hover:border-cv-text-muted focus:border-cv-accent focus:shadow-none focus:ring-2 focus:ring-cv-accent focus:ring-offset-1 focus:ring-offset-cv-surface aria-invalid:border-cv-blocker aria-invalid:ring-2 aria-invalid:ring-cv-blocker-soft aria-invalid:ring-offset-0 disabled:cursor-not-allowed disabled:border-cv-border disabled:bg-cv-surface-muted disabled:text-cv-text-muted disabled:shadow-none";

export const TextInput = ({ className, type, ...rest }: ComponentProps<"input">) => {
  return <input className={cx(controlClasses, "min-h-11", className)} type={type ?? "text"} {...rest} />;
};

export const TextArea = ({ className, ...rest }: ComponentProps<"textarea">) => {
  return <textarea className={cx(controlClasses, "min-h-32 resize-y", className)} {...rest} />;
};
