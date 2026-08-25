import { cx } from "./cx";

export interface ViewSwitchOption<TValue extends string> {
  label: string;
  value: TValue;
}

interface ViewSwitchProps<TValue extends string> {
  label: string;
  onChange: (value: TValue) => void;
  options: ViewSwitchOption<TValue>[];
  value: TValue;
}

/* A.4 responsive fallback: the editor/preview split collapses into one switch. Buttons
   with aria-pressed keep it a real control without a tab/panel contract the panes do
   not have, and switching views never discards unsaved text. */
export const ViewSwitch = <TValue extends string>({
  label,
  onChange,
  options,
  value,
}: ViewSwitchProps<TValue>) => {
  return (
    <div
      aria-label={label}
      className="inline-flex gap-1 rounded-surface border border-cv-border bg-cv-surface-muted p-1 shadow-inner"
      role="group"
    >
      {options.map((option) => (
        <button
          aria-pressed={option.value === value}
          className={cx(
            "min-h-11 rounded-control px-4 text-support font-semibold transition-all duration-200",
            option.value === value
              ? "bg-cv-surface text-cv-accent shadow-surface"
              : "text-cv-text-muted hover:bg-cv-surface-muted",
          )}
          key={option.value}
          onClick={() => onChange(option.value)}
          type="button"
        >
          {option.label}
        </button>
      ))}
    </div>
  );
};
