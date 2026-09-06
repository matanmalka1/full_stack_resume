import { type ReactNode, useId } from "react";

import { cx } from "./cx";

interface SwitchProps {
  checked: boolean;
  children: ReactNode;
  /* The consequence of turning it on, read with the label rather than after it. */
  description?: ReactNode;
  disabled?: boolean;
  onChange: (checked: boolean) => void;
}

/* An explicit acknowledgement, for the one kind of decision a checkbox understates: the
   reader is accepting a stated risk, not ticking an option. `role="switch"` is what says
   so - it announces "on/off" rather than "checked", and the track carries the state at a
   size a 16px box does not.

   The knob travels on the logical axis (`start`), so the shell's RTL direction moves it
   toward the reading end rather than to a hard-coded left. */
export const Switch = ({ checked, children, description, disabled = false, onChange }: SwitchProps) => {
  const id = useId();
  const labelId = `${id}-label`;
  const descriptionId = `${id}-description`;

  return (
    <div className="flex items-start gap-3">
      <button
        aria-checked={checked}
        aria-describedby={description === undefined ? undefined : descriptionId}
        aria-labelledby={labelId}
        className={cx(
          "relative mt-0.5 inline-flex h-6 w-11 shrink-0 items-center rounded-pill border transition-colors duration-200 disabled:cursor-not-allowed disabled:opacity-60",
          checked ? "border-cv-accent bg-cv-accent" : "border-cv-border-strong bg-cv-surface-sunken",
        )}
        disabled={disabled}
        onClick={() => onChange(!checked)}
        role="switch"
        type="button"
      >
        <span
          aria-hidden="true"
          className={cx(
            "absolute size-4 rounded-pill bg-cv-surface shadow-surface transition-[inset-inline-start] duration-200",
            checked ? "start-6" : "start-1",
          )}
        />
      </button>
      <span className="min-w-0 flex-1">
        <span className="block text-body font-medium text-cv-text" id={labelId}>
          {children}
        </span>
        {description === undefined ? null : (
          <span className="mt-1 block text-support leading-6 text-cv-text-muted" id={descriptionId}>
            {description}
          </span>
        )}
      </span>
    </div>
  );
};
