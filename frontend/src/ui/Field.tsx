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
      <div className="flex flex-wrap items-baseline gap-x-2">
        <label className="text-support font-medium text-cv-text" htmlFor={id}>
          {label}
        </label>
        {optional ? (
          /* A chip rather than more label text - and, deliberately, a sibling of the
             label rather than a child of it. Nested inside, its own text became part of
             the label's accessible name ("דגש" read as "דגש אופציונלי"), which is a real
             control name a reader or a test can no longer address by the field's own
             name alone. As a sibling it stays exactly where it was drawn - same row,
             same gap - without joining the name the label puts on the control. */
          <span className="rounded-pill bg-cv-surface-sunken px-2 py-0.5 text-caption font-normal text-cv-text-muted">
            אופציונלי
          </span>
        ) : null}
      </div>
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
