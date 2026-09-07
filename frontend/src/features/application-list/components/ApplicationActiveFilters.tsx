import { X } from "lucide-react";
import type { ReactNode } from "react";

import type { ActivityFilter, ApplicationPreset, ApplicationSort, PreparationState } from "@/api/contracts";
import { preparationStateLabels } from "@/features/preparation";
import { Button } from "@/ui/Button";
import { type RecruitmentStageId, recruitmentStages } from "../model/recruitmentStages";

const activityLabels: Record<ActivityFilter, string> = { all: "הכול", closed: "סגורות", open: "פעילות" };
const presetLabels: Record<ApplicationPreset, string> = {
  active_interviews: "ראיונות פעילים",
  needs_attention: "דורש טיפול",
  ready_to_send: "מוכן לשליחה",
};
const sortLabels: Record<ApplicationSort, string> = {
  company: "לפי חברה",
  created: "נוצר לאחרונה",
  stage: "לפי מצב קורות החיים",
  updated: "עודכן לאחרונה",
};

interface ApplicationActiveFiltersProps {
  activity: ActivityFilter;
  activePreset: ApplicationPreset | undefined;
  preparationState: PreparationState | undefined;
  recruitmentStage: RecruitmentStageId | null;
  search: string;
  sort: ApplicationSort;
  onActivityChange: (activity: ActivityFilter) => void;
  onClearAll: () => void;
  onPreparationStateChange: (stage: PreparationState | undefined) => void;
  onPresetClear: () => void;
  onRecruitmentStageChange: (stage: RecruitmentStageId | null) => void;
  onSearchChange: (search: string) => void;
  onSortChange: (sort: ApplicationSort) => void;
}

const FilterChip = ({ children, onRemove }: { children: ReactNode; onRemove: () => void }) => (
  <Button className="gap-1" onClick={onRemove} size="compact" variant="ghost">
    {children}
    <X aria-hidden="true" className="size-3" />
  </Button>
);

export const ApplicationActiveFilters = ({
  activity,
  activePreset,
  preparationState,
  recruitmentStage,
  search,
  sort,
  onActivityChange,
  onClearAll,
  onPreparationStateChange,
  onPresetClear,
  onRecruitmentStageChange,
  onSearchChange,
  onSortChange,
}: ApplicationActiveFiltersProps) => {
  const hasActiveFilters =
    activePreset !== undefined ||
    search !== "" ||
    activity !== "open" ||
    preparationState !== undefined ||
    recruitmentStage !== null ||
    sort !== "updated";

  if (!hasActiveFilters) return null;

  return (
    <div className="mt-2 flex flex-wrap items-center gap-1.5 border-t border-cv-border pt-2">
      <span className="text-support font-semibold text-cv-text-muted">מסננים פעילים:</span>
      {activePreset === undefined ? null : (
        <FilterChip onRemove={onPresetClear}>{presetLabels[activePreset]}</FilterChip>
      )}
      {search === "" ? null : <FilterChip onRemove={() => onSearchChange("")}>חיפוש: {search}</FilterChip>}
      {activity === "open" ? null : (
        <FilterChip onRemove={() => onActivityChange("open")}>{activityLabels[activity]}</FilterChip>
      )}
      {preparationState === undefined ? null : (
        <FilterChip onRemove={() => onPreparationStateChange(undefined)}>
          {preparationStateLabels[preparationState]}
        </FilterChip>
      )}
      {recruitmentStage === null ? null : (
        <FilterChip onRemove={() => onRecruitmentStageChange(null)}>
          {recruitmentStages.find((stage) => stage.id === recruitmentStage)?.label}
        </FilterChip>
      )}
      {sort === "updated" ? null : <FilterChip onRemove={() => onSortChange("updated")}>{sortLabels[sort]}</FilterChip>}
      <Button onClick={onClearAll} size="compact" variant="ghost">
        ניקוי הכול
      </Button>
    </div>
  );
};
