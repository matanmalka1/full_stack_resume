import type { InputHTMLAttributes, ReactNode } from "react";

import { cx } from "./cx";

interface CheckboxProps extends Omit<InputHTMLAttributes<HTMLInputElement>, "type"> {
  children: ReactNode;
  hint?: ReactNode;
}

/* A.5: every control carries a visible Hebrew label, so the label is a required child
   rather than an optional prop. */
export const Checkbox = ({ children, className, hint, ...rest }: CheckboxProps) => {
  return (
    <label
      className={cx(
        "flex min-h-11 items-start gap-3 rounded-control border border-transparent px-3 py-2.5 text-body transition-colors hover:border-cv-border hover:bg-cv-surface-muted",
        className,
      )}
    >
      <input
        className="mt-1 size-5 shrink-0 rounded-control border-cv-border-strong accent-cv-accent"
        type="checkbox"
        {...rest}
      />
      <span className="flex flex-col gap-1">
        <span>{children}</span>
        {hint === undefined ? null : <span className="text-support text-cv-text-muted">{hint}</span>}
      </span>
    </label>
  );
};
