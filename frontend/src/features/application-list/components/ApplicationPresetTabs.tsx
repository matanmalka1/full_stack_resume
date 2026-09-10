import type { ApplicationPreset } from "@/api/contracts";
import { cx } from "@/ui/cx";

export type PresetSelection = ApplicationPreset | "all";

interface ApplicationPresetTabsProps {
  counts: Record<string, number> | undefined;
  onSelect: (preset: PresetSelection) => void;
  value: PresetSelection;
}

/* The four named slices of the board, drawn as one filter.

   These are the same counts and the same query the metric cards ran. What is gone is
   the framing: a row of tinted, iconed tiles with display-sized numbers reads as a
   dashboard the reader is meant to study, while this is the one question the list can
   be narrowed by - a control, and sized like one. It sits in the page masthead beside
   the title, ahead of the filter bar, because it is the first cut the reader makes.
   The screen's weight belongs to the rows underneath.

   `דורש טיפול` keeps a warning tint on its count while it is unselected, because that
   slice is the only one the reader needs to notice without looking for it. */
const presetTabs: readonly { id: PresetSelection; label: string; urgent: boolean }[] = [
  { id: "all", label: "הכול", urgent: false },
  { id: "active_interviews", label: "ראיונות פעילים", urgent: false },
  { id: "ready_to_send", label: "מוכן לשליחה", urgent: false },
  { id: "needs_attention", label: "דורש טיפול", urgent: true },
];

export const ApplicationPresetTabs = ({ counts, onSelect, value }: ApplicationPresetTabsProps) => (
  // A non-form group of toggle buttons; role="group" is the ARIA authoring-practices
  // pattern here, and none of the suggested native tags (fieldset, etc.) fit.
  // oxlint-disable-next-line jsx-a11y/prefer-tag-over-role
  <div aria-label="סינון מהיר לפי מצב" className="flex flex-wrap items-center gap-1" role="group">
    {presetTabs.map(({ id, label, urgent }) => {
      const active = id === value;
      const count = counts?.[id];

      return (
        <button
          aria-pressed={active}
          className={cx(
            "inline-flex min-h-9 items-center gap-2 rounded-control px-2.5 text-support font-semibold transition-colors",
            active ? "bg-cv-accent text-cv-on-accent" : "bg-cv-surface-muted text-cv-text-muted hover:text-cv-text",
          )}
          key={id}
          onClick={() => onSelect(id)}
          type="button"
        >
          {label}
          <span
            className={cx(
              "rounded-pill px-1.5 text-support font-bold tabular-nums",
              active
                ? "bg-cv-on-accent/20 text-cv-on-accent"
                : urgent && count !== undefined && count > 0
                  ? "bg-cv-warning-soft text-cv-warning"
                  : "bg-cv-surface text-cv-text-muted",
            )}
          >
            {count ?? "—"}
          </span>
        </button>
      );
    })}
  </div>
);
