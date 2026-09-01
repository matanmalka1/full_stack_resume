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
}

/* Wires label, hint, and error to one control so no call site invents its own ids.
   The control keeps the RTL shell even when its value is an LTR island (A.3). */
export const Field = ({ children, className, error, hint, label }: FieldProps) => {
  const id = useId();
  const hintId = `${id}-hint`;
  const errorId = `${id}-error`;
  const describedBy = cx(hint === undefined ? undefined : hintId, error === undefined ? undefined : errorId);

  return (
    <div className={cx("flex flex-col gap-1.5", className)}>
      <label className="text-support font-medium text-cv-text" htmlFor={id}>
        {label}
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
