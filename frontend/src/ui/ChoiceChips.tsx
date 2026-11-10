import { Check } from "lucide-react";
import { type ReactNode, useId } from "react";

import { cx } from "./cx";

export interface ChoiceChipOption<TValue extends string> {
  label: string;
  value: TValue;
}

interface ChoiceChipsProps<TValue extends string> {
  disabled?: boolean;
  label: ReactNode;
  onChange: (value: TValue) => void;
  options: readonly ChoiceChipOption<TValue>[];
  /* A second set drawn under a divider with dashed edges: the answers that end the
     matter - a rejection, a withdrawal - kept apart from the ones that move it on. */
  secondaryOptions?: readonly ChoiceChipOption<TValue>[];
  value: TValue | null;
}

/* One answer out of several, drawn as a wrapping row of pills - a fact's kind,
   a setting. The pills are native radio inputs in a fieldset, as in
   `SegmentedControl`: arrow keys move between them, the legend names the group, and the
   focus ring is drawn on the pill through `has-[:focus-visible]`. The chosen pill fills
   with the accent and carries a check, so the choice does not rest on colour alone. */
export const ChoiceChips = <TValue extends string>({
  disabled = false,
  label,
  onChange,
  options,
  secondaryOptions,
  value,
}: ChoiceChipsProps<TValue>) => {
  const name = useId();

  const chip = (option: ChoiceChipOption<TValue>, secondary: boolean) => {
    const active = option.value === value;
    return (
      <label
        className={cx(
          "inline-flex h-9.5 cursor-pointer items-center gap-1.5 rounded-pill border px-3.5 text-label transition-colors has-[:focus-visible]:outline-2 has-[:focus-visible]:outline-offset-2 has-[:focus-visible]:outline-cv-focus has-[:disabled]:cursor-not-allowed has-[:disabled]:opacity-60",
          active
            ? "border-cv-accent bg-cv-accent font-bold text-cv-on-accent"
            : cx(
                "font-normal text-cv-text-muted hover:text-cv-text",
                secondary ? "border-dashed border-cv-border-strong" : "border-cv-border hover:border-cv-border-strong",
              ),
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
        {active ? <Check aria-hidden="true" className="size-3.5 shrink-0" strokeWidth={2.5} /> : null}
        {option.label}
      </label>
    );
  };

  return (
    <fieldset className="min-w-0" disabled={disabled}>
      <legend className="mb-2.5 text-label font-bold text-cv-text">{label}</legend>
      <div className="flex flex-wrap gap-2">{options.map((option) => chip(option, false))}</div>
      {secondaryOptions === undefined || secondaryOptions.length === 0 ? null : (
        <div className="mt-2.5 flex flex-wrap gap-2 border-t border-cv-hairline pt-2.5">
          {secondaryOptions.map((option) => chip(option, true))}
        </div>
      )}
    </fieldset>
  );
};
