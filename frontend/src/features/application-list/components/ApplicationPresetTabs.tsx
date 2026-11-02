import type { ApplicationPreset } from "@/api/contracts";
import { FilterChip } from "@/ui/FilterChip";

type PresetSelection = ApplicationPreset | "all";

interface ApplicationPresetTabsProps {
  counts: Record<string, number> | undefined;
  onSelect: (preset: PresetSelection) => void;
  value: PresetSelection;
}

/* The board's named slices, drawn as one row of quick filters - the only narrowing the
   board offers. Finding one record by name is the quick search's.

   "דורש טיפול" is the one slice that asks for the reader rather than describing the board:
   its count is a filled disc and its edge stronger, while it holds anything.

   On a phone the chips stay on one line and the row scrolls sideways, bleeding to the
   screen's edges so a chip cut off at the edge says there is more. */
const presetTabs: readonly { id: PresetSelection; label: string }[] = [
  { id: "all", label: "הכל" },
  { id: "needs_attention", label: "דורש טיפול" },
  { id: "active_interviews", label: "ראיונות פעילים" },
  { id: "ready_to_send", label: "מוכן לשליחה" },
];

export const ApplicationPresetTabs = ({ counts, onSelect, value }: ApplicationPresetTabsProps) => (
  // A non-form group of toggle buttons; role="group" is the ARIA authoring-practices
  // pattern here, and none of the suggested native tags (fieldset, etc.) fit.
  <div
    aria-label="סינון מהיר לפי מצב"
    className="-mx-4 flex items-center gap-2 overflow-x-auto px-4 py-0.5 [scrollbar-width:none] sm:-mx-6 sm:px-6 lg:mx-0 lg:flex-wrap lg:overflow-visible lg:px-0 [&::-webkit-scrollbar]:hidden"
    // oxlint-disable-next-line jsx-a11y/prefer-tag-over-role
    role="group"
  >
    {presetTabs.map(({ id, label }) => {
      const count = counts?.[id] ?? 0;
      return (
        <FilterChip
          count={count}
          countVariant={id === "needs_attention" && count > 0 ? "badge" : "plain"}
          key={id}
          onClick={() => onSelect(id)}
          pressed={id === value}
        >
          {/* The space keeps the label and its count two words in the chip's name. */}
          {label}{" "}
        </FilterChip>
      );
    })}
  </div>
);
