import type { ComponentProps } from "react";

import { cx } from "./cx";

/* ComponentProps rather than the attribute types alone: these carry `ref`, which is
   how React Hook Form binds an uncontrolled field to the primitive. */
export const controlClasses =
  "block w-full rounded-control border border-cv-border-strong bg-cv-surface px-3.5 py-2.5 text-body text-cv-text shadow-inner transition-[border-color,box-shadow,background-color] duration-200 placeholder:text-cv-text-muted hover:border-cv-text-muted focus:border-cv-accent focus:ring-4 focus:ring-cv-accent-soft disabled:bg-cv-surface-muted aria-invalid:border-cv-blocker aria-invalid:ring-cv-blocker-soft";

export const TextInput = ({
  className,
  type,
  ...rest
}: ComponentProps<"input">) => {
  return <input className={cx(controlClasses, "min-h-11", className)} type={type ?? "text"} {...rest} />;
};

export const TextArea = ({ className, ...rest }: ComponentProps<"textarea">) => {
  return <textarea className={cx(controlClasses, "min-h-32", className)} {...rest} />;
};
