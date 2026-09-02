import type { ComponentProps } from "react";

import { cx } from "./cx";

/* ComponentProps rather than the attribute types alone: these carry `ref`, which is
   how React Hook Form binds an uncontrolled field to the primitive. */

/* The resting edge is the strong border token, the same one the checkbox draws itself
   with: a control's boundary is the only thing telling the eye where the field starts,
   and the decorative border it used to carry sat at about 1.1:1 against the surface -
   invisible on the canvas, and short of the 3:1 a boundary owes. Weight now comes from
   that edge rather than from an inset hairline, which under a real border only muddied
   it. Hover darkens to body text, a step the previous pairing did not make since hover
   and rest resolved to the same hex. Focus offsets the accent ring so ring and border
   stay legible instead of blurring into one thick edge. Invalid carries its own ring at
   rest rather than only once focused.

   Height stays at the call sites: `cx` is a plain join with no conflict resolution,
   so a `min-h` here would collide with the textarea's own. */
export const controlClasses =
  "block w-full rounded-control border border-cv-border-strong bg-cv-surface px-3.5 py-2.5 text-body text-cv-text transition-[border-color,box-shadow,background-color] duration-200 placeholder:text-cv-text-muted hover:border-cv-text focus:border-cv-accent focus:ring-2 focus:ring-cv-accent focus:ring-offset-1 focus:ring-offset-cv-surface aria-invalid:border-cv-blocker aria-invalid:ring-2 aria-invalid:ring-cv-blocker-soft aria-invalid:ring-offset-0 disabled:cursor-not-allowed disabled:border-cv-border disabled:bg-cv-surface-muted disabled:text-cv-text-muted";

export const TextInput = ({ className, type, ...rest }: ComponentProps<"input">) => {
  return <input className={cx(controlClasses, "min-h-11", className)} type={type ?? "text"} {...rest} />;
};

export const TextArea = ({ className, ...rest }: ComponentProps<"textarea">) => {
  return <textarea className={cx(controlClasses, "min-h-32 resize-y", className)} {...rest} />;
};
