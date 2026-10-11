import type { LucideIcon } from "lucide-react";
import { type ReactNode, useId } from "react";

import { cx } from "./cx";

interface SegmentedOption<TValue extends string> {
  icon?: LucideIcon;
  label: string;
  value: TValue;
}

interface SegmentedControlProps<TValue extends string> {
  description?: ReactNode;
  disabled?: boolean;
  label: ReactNode;
  onChange: (value: TValue) => void;
  options: readonly SegmentedOption<TValue>[];
  value: TValue;
}

/* One choice out of a few, all visible at once. It replaces a pair of switches that
   encoded a three-way setting - "follow the system" on one, "dark" on the other, which
   was disabled until the first was turned off - with the three answers side by side.

   The segments are native radio inputs in a fieldset: arrow keys move between them, a
   screen reader announces "1 of 3", and the legend names the group. The input itself is
   visually hidden and the label drawn as the segment, so the focus ring is drawn on the
   segment through `has-[:focus-visible]`. */
export const SegmentedControl = <TValue extends string>({
  description,
  disabled = false,
  label,
  onChange,
  options,
  value,
}: SegmentedControlProps<TValue>) => {
  const name = useId();
  const descriptionId = `${name}-description`;

  return (
    <fieldset
      aria-describedby={description === undefined ? undefined : descriptionId}
      className="min-w-0"
      disabled={disabled}
    >
      <legend className="text-body font-medium text-cv-text">{label}</legend>
      {description === undefined ? null : (
        <p className="mt-1 text-support leading-6 text-cv-text-muted" id={descriptionId}>
          {description}
        </p>
      )}
      <div className="mt-2 inline-flex max-w-full gap-1 rounded-control border border-cv-border bg-cv-surface-muted p-1">
        {options.map((option) => {
          const Icon = option.icon;
          const active = option.value === value;
          return (
            <label
              className={cx(
                "inline-flex min-h-10 min-w-0 cursor-pointer items-center justify-center gap-1.5 rounded-control px-3 text-support font-semibold transition-colors has-[:focus-visible]:outline-2 has-[:focus-visible]:outline-offset-2 has-[:focus-visible]:outline-cv-focus has-[:disabled]:cursor-not-allowed has-[:disabled]:opacity-60",
                active
                  ? "bg-cv-surface text-cv-text shadow-floating"
                  : "text-cv-text-muted hover:bg-cv-surface hover:text-cv-text",
              )}
              key={option.value}
            >
              <input
                checked={active}
                className="sr-only"
                name={name}
                onChange={() => onChange(option.value)}
                type="radio"
                value={option.value}
              />
              {Icon === undefined ? null : <Icon aria-hidden="true" className="size-icon-md shrink-0" />}
              <span className="truncate">{option.label}</span>
            </label>
          );
        })}
      </div>
    </fieldset>
  );
};
