import type { LucideIcon } from "lucide-react";

import { cx } from "./cx";
import { Tooltip } from "./Tooltip";

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
  /* Below the large breakpoint the switch spans its row as a segmented control, every
     option an equal segment with its label drawn beside its icon - the board's
     cards/stages choice on a phone. From the large breakpoint it is the compact switch. */
  stretch?: boolean;
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
  stretch = false,
  value,
}: ViewSwitchProps<TValue>) => {
  return (
    <div
      aria-label={label}
      className={cx(
        "inline-flex gap-0.5 rounded-control-sm bg-cv-surface-muted p-0.75",
        stretch && "max-lg:flex max-lg:w-full",
      )}
      // A non-form group of toggle buttons; role="group" is the ARIA authoring-practices
      // pattern here, and none of the suggested native tags (fieldset, etc.) fit.
      // oxlint-disable-next-line jsx-a11y/prefer-tag-over-role
      role="group"
    >
      {options.map((option) => {
        const Icon = option.icon;
        const active = option.value === value;
        const iconOnly = Icon !== undefined && !showLabels;

        const button = (
          <button
            aria-label={Icon === undefined ? undefined : option.label}
            aria-pressed={active}
            className={cx(
              "min-h-8.5 rounded-item text-support transition-colors duration-200",
              Icon === undefined || showLabels ? "inline-flex items-center gap-1.5 px-3.5" : "px-2",
              active
                ? "bg-cv-surface font-bold text-cv-text shadow-segment"
                : "font-medium text-cv-text-muted hover:text-cv-text",
              stretch &&
                "max-lg:inline-flex max-lg:flex-1 max-lg:items-center max-lg:justify-center max-lg:gap-1.5 max-lg:px-3",
              iconOnly && stretch && "max-lg:w-full",
            )}
            key={option.value}
            onClick={() => onChange(option.value)}
            type="button"
          >
            {Icon === undefined ? null : <Icon aria-hidden="true" className="size-icon-md" />}
            {Icon === undefined ? (
              option.label
            ) : showLabels || stretch ? (
              <span className={cx("hidden", showLabels && "sm:inline", stretch && "max-lg:inline")}>
                {option.label}
              </span>
            ) : null}
          </button>
        );

        /* An icon-only option names itself in the shared tooltip, not a native title=. */
        return iconOnly ? (
          <Tooltip className={cx(stretch && "max-lg:flex-1")} key={option.value} label={option.label}>
            {button}
          </Tooltip>
        ) : (
          button
        );
      })}
    </div>
  );
};
