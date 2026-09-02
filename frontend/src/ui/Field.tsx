import { type ReactNode, useId } from "react";

import { cx } from "./cx";

interface FieldControl {
  "aria-describedby": string | undefined;
  "aria-invalid": boolean | undefined;
  id: string;
}

interface FieldProps {
  children: (control: FieldControl) => ReactNode;
  className?: string;
  error?: string;
  hint?: ReactNode;
  label: ReactNode;
  /* Nearly every field on a form is required, so saying so on each label is noise that
     hides the one fact worth reading: which field may be left empty. Only the exception
     is marked. */
  optional?: boolean;
}

/* Wires label, hint, and error to one control so no call site invents its own ids.
   The control keeps the RTL shell even when its value is an LTR island (A.3). */
export const Field = ({ children, className, error, hint, label, optional = false }: FieldProps) => {
  const id = useId();
  const hintId = `${id}-hint`;
  const errorId = `${id}-error`;
  const describedBy = cx(hint === undefined ? undefined : hintId, error === undefined ? undefined : errorId);

  return (
    <div className={cx("flex flex-col gap-1.5", className)}>
      <label className="flex flex-wrap items-baseline gap-x-2 text-support font-medium text-cv-text" htmlFor={id}>
        {label}
        {optional ? (
          /* A chip rather than more label text: at the label's own size and weight it
             read as part of the field's name instead of as a note about it. */
          <span className="rounded-pill bg-cv-surface-sunken px-2 py-0.5 text-[0.75rem] font-normal text-cv-text-muted">
            אופציונלי
          </span>
        ) : null}
      </label>
      {hint === undefined ? null : (
        <p className="text-support text-cv-text-muted" id={hintId}>
          {hint}
        </p>
      )}
      {children({
        "aria-describedby": describedBy === "" ? undefined : describedBy,
        "aria-invalid": error === undefined ? undefined : true,
        id,
      })}
      {error === undefined ? null : (
        <p className="text-support font-medium text-cv-blocker" id={errorId}>
          {error}
        </p>
      )}
    </div>
  );
};
