import type { LucideIcon } from "lucide-react";

import { cx } from "./cx";
import { surfaceClasses } from "./Surface";

interface ViewSwitchOption<TValue extends string> {
  /* An icon-only option renders its icon instead of `label` text; `label` still names
     the button for assistive tech and its hover title. */
  icon?: LucideIcon;
  label: string;
  value: TValue;
}

interface ViewSwitchProps<TValue extends string> {
  label: string;
  onChange: (value: TValue) => void;
  options: readonly ViewSwitchOption<TValue>[];
  value: TValue;
}

/* A.4 responsive fallback: the editor/preview split collapses into one switch. Buttons
   with aria-pressed keep it a real control without a tab/panel contract the panes do
   not have, and switching views never discards unsaved text. */
export const ViewSwitch = <TValue extends string>({ label, onChange, options, value }: ViewSwitchProps<TValue>) => {
  return (
    <div
      aria-label={label}
      className={surfaceClasses("inline-flex gap-1 bg-cv-surface-muted p-1 shadow-inner")}
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
              Icon === undefined ? "px-4 text-support font-semibold" : "p-2",
              active ? "bg-cv-surface text-cv-accent shadow-surface" : "text-cv-text-muted hover:bg-cv-surface-muted",
            )}
            key={option.value}
            onClick={() => onChange(option.value)}
            title={Icon === undefined ? undefined : option.label}
            type="button"
          >
            {Icon === undefined ? option.label : <Icon aria-hidden="true" className="size-4" />}
          </button>
        );
      })}
    </div>
  );
};
