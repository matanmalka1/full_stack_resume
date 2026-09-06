import { Check } from "lucide-react";
import { type InputHTMLAttributes, type ReactNode, useId } from "react";

import { cx } from "./cx";

interface CheckboxProps extends Omit<InputHTMLAttributes<HTMLInputElement>, "type"> {
  children: ReactNode;
  hint?: ReactNode;
}

/* A.5: every control carries a visible Hebrew label, so the label is a required child
   rather than an optional prop.

   The box is drawn by a sibling `<span>`, not by the input itself. A native checkbox
   styled only with `accent-color` is still the browser's own control underneath: its
   border-radius and background are ignored outright in most engines, so the box read as
   an unstyled OS square with a colour tint rather than a control that matched the radius,
   border, and focus ring every other input on this design system carries.

   The input stays exactly what it was - a real, keyboard-operable checkbox, focusable and
   labelled the same way - and is only made invisible (`opacity-0`, never `hidden` or
   `display:none`), so it keeps its place in the tab order and its native toggle behaviour
   while every visible pixel is drawn by the box and tick beside it, from the same tokens
   as everywhere else. */
export const Checkbox = ({
  "aria-describedby": describedBy,
  "aria-labelledby": labelledBy,
  children,
  className,
  hint,
  id,
  ...rest
}: CheckboxProps) => {
  const generatedId = useId();
  const inputId = id ?? generatedId;
  const labelId = `${inputId}-label`;
  const hintId = `${inputId}-hint`;
  const descriptionIds = [describedBy, hint === undefined ? undefined : hintId].filter(Boolean).join(" ") || undefined;
  const labelIds = [labelledBy, labelId].filter(Boolean).join(" ");

  return (
    <label
      className={cx(
        "flex min-h-11 items-start gap-3 rounded-control border border-transparent px-3 py-2.5 text-body transition-colors hover:border-cv-border hover:bg-cv-surface-muted has-[:disabled]:cursor-not-allowed",
        className,
      )}
    >
      <span className="relative mt-1 inline-flex size-5 shrink-0">
        <input
          aria-describedby={descriptionIds}
          aria-labelledby={labelIds}
          className="peer absolute inset-0 size-5 cursor-pointer opacity-0 disabled:cursor-not-allowed"
          id={inputId}
          type="checkbox"
          {...rest}
        />
        <span
          aria-hidden="true"
          className="pointer-events-none absolute inset-0 rounded-control border-2 border-cv-border-strong bg-cv-surface transition-colors peer-hover:border-cv-text peer-checked:border-cv-accent peer-checked:bg-cv-accent peer-focus-visible:ring-2 peer-focus-visible:ring-cv-accent peer-focus-visible:ring-offset-1 peer-focus-visible:ring-offset-cv-surface peer-disabled:border-cv-border peer-disabled:bg-cv-surface-muted"
        />
        <Check
          aria-hidden="true"
          className="pointer-events-none absolute inset-0 m-auto size-3.5 text-cv-on-accent opacity-0 transition-opacity peer-checked:opacity-100"
          strokeWidth={3}
        />
      </span>
      <span className="flex flex-col gap-1">
        <span id={labelId}>{children}</span>
        {hint === undefined ? null : (
          <span className="text-support text-cv-text-muted" id={hintId}>
            {hint}
          </span>
        )}
      </span>
    </label>
  );
};
