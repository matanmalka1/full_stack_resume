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

   Each option is one compact pill. The count stays typographically distinct without
   becoming a second badge inside the control. */
const presetTabs: readonly { id: PresetSelection; label: string }[] = [
  { id: "all", label: "הכל" },
  { id: "active_interviews", label: "ראיונות פעילים" },
  { id: "ready_to_send", label: "מוכן לשליחה" },
  { id: "needs_attention", label: "דורש טיפול" },
];

export const ApplicationPresetTabs = ({ counts, onSelect, value }: ApplicationPresetTabsProps) => (
  // A non-form group of toggle buttons; role="group" is the ARIA authoring-practices
  // pattern here, and none of the suggested native tags (fieldset, etc.) fit.
  // oxlint-disable-next-line jsx-a11y/prefer-tag-over-role
  <div aria-label="סינון מהיר לפי מצב" className="flex flex-wrap items-center gap-1.5" role="group">
    {presetTabs.map(({ id, label }) => {
      const active = id === value;
      const count = counts?.[id];

      return (
        <button
          aria-pressed={active}
          className={cx(
            "inline-flex min-h-9 items-center gap-2 rounded-pill border px-3 text-support font-medium transition-colors",
            active
              ? "border-cv-accent bg-cv-accent text-cv-on-accent"
              : "border-cv-border bg-cv-surface-muted text-cv-text-muted hover:border-cv-border-strong hover:text-cv-text",
          )}
          key={id}
          onClick={() => onSelect(id)}
          type="button"
        >
          {label}
          <span
            className={cx(
              "text-support font-semibold tabular-nums",
              active ? "text-cv-on-accent" : "text-cv-text-muted",
            )}
          >
            {count ?? "—"}
          </span>
        </button>
      );
    })}
  </div>
);
