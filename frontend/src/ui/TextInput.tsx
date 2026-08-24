import type { InputHTMLAttributes, TextareaHTMLAttributes } from "react";

import { cx } from "./cx";

export const controlClasses =
  "block w-full rounded-control border border-cv-border-strong bg-cv-surface px-3 py-2 text-body text-cv-text placeholder:text-cv-text-muted disabled:bg-cv-surface-muted aria-invalid:border-cv-blocker";

export const TextInput = ({
  className,
  type,
  ...rest
}: InputHTMLAttributes<HTMLInputElement>) => {
  return <input className={cx(controlClasses, "min-h-11", className)} type={type ?? "text"} {...rest} />;
};

export const TextArea = ({ className, ...rest }: TextareaHTMLAttributes<HTMLTextAreaElement>) => {
  return <textarea className={cx(controlClasses, "min-h-32", className)} {...rest} />;
};
