import type { LucideIcon } from "lucide-react";

import { cx } from "./cx";
import { surfaceClasses } from "./surface";

interface ViewSwitchOption<TValue extends string> {
  /* `label` always names icon options for assistive tech. Callers may also expose the
     short label visually where the switch would otherwise be ambiguous. */
  icon?: LucideIcon;
  label: string;
  value: TValue;
}

interface ViewSwitchProps<TValue extends string> {
  label: string;
  onChange: (value: TValue) => void;
  options: readonly ViewSwitchOption<TValue>[];
  showLabels?: boolean;
  value: TValue;
}

/* A.4 responsive fallback: the editor/preview split collapses into one switch. Buttons
   with aria-pressed keep it a real control without a tab/panel contract the panes do
   not have, and switching views never discards unsaved text. */
export const ViewSwitch = <TValue extends string>({
  label,
  onChange,
  options,
  showLabels = false,
  value,
}: ViewSwitchProps<TValue>) => {
  return (
    <div
      aria-label={label}
      className={surfaceClasses("inline-flex gap-1 bg-cv-surface-muted p-1 shadow-inner")}
      // A non-form group of toggle buttons; role="group" is the ARIA authoring-practices
      // pattern here, and none of the suggested native tags (fieldset, etc.) fit.
      // oxlint-disable-next-line jsx-a11y/prefer-tag-over-role
      role="group"
    >
      {options.map((option) => {
        const Icon = option.icon;
        const active = option.value === value;

        return (
          <button
            aria-label={Icon === undefined ? undefined : option.label}
            aria-pressed={active}
            className={cx(
              "min-h-11 rounded-control transition-all duration-200",
              Icon === undefined || showLabels
                ? "inline-flex items-center gap-1.5 px-3 text-support font-semibold"
                : "p-2",
              active ? "bg-cv-surface text-cv-accent shadow-surface" : "text-cv-text-muted hover:bg-cv-surface-muted",
            )}
            key={option.value}
            onClick={() => onChange(option.value)}
            title={Icon === undefined || showLabels ? undefined : option.label}
            type="button"
          >
            {Icon === undefined ? null : <Icon aria-hidden="true" className="size-4" />}
            {Icon === undefined ? (
              option.label
            ) : showLabels ? (
              <span className="hidden sm:inline">{option.label}</span>
            ) : null}
          </button>
        );
      })}
    </div>
  );
};
