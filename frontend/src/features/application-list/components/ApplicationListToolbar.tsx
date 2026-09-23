import { Search } from "lucide-react";

import type { ActivityFilter, PreparationState } from "@/api/contracts";
import { preparationStateLabels } from "@/features/preparation";
import { Button } from "@/ui/Button";
import { Field } from "@/ui/Field";
import { Input } from "@/ui/Input";
import { Select } from "@/ui/Select";
import { flatSurfaceClasses } from "@/ui/surface";
import { ViewSwitch } from "@/ui/ViewSwitch";
import { type ViewMode, viewModeOptions } from "../model/applicationViews";
import { type RecruitmentStageId, recruitmentStages } from "../model/recruitmentStages";

const activityLabels: Record<ActivityFilter, string> = {
  open: "פעילות",
  closed: "סגורות",
  all: "הכול",
};

// Let each select fit its options without pushing the other controls off the row.
const fieldClasses = "w-full min-w-0 sm:w-auto sm:min-w-36 sm:max-w-64";

interface ApplicationListToolbarProps {
  activity: ActivityFilter;
  filtered: boolean;
  preparationState: PreparationState | undefined;
  recruitmentStage: RecruitmentStageId | null;
  recruitmentStageCounts: Partial<Record<RecruitmentStageId, number>>;
  resultSummary: string;
  search: string;
  stageCounts: Partial<Record<PreparationState, number>>;
  viewMode: ViewMode;
  onActivityChange: (activity: ActivityFilter) => void;
  onClearFilters: () => void;
  onPreparationStateChange: (stage: PreparationState | undefined) => void;
  onRecruitmentStageChange: (stage: RecruitmentStageId | null) => void;
  onSearchChange: (search: string) => void;
  onViewModeChange: (view: ViewMode) => void;
}

export const ApplicationListToolbar = ({
  activity,
  filtered,
  preparationState,
  recruitmentStage,
  recruitmentStageCounts,
  resultSummary,
  search,
  stageCounts,
  viewMode,
  onActivityChange,
  onClearFilters,
  onPreparationStateChange,
  onRecruitmentStageChange,
  onSearchChange,
  onViewModeChange,
}: ApplicationListToolbarProps) => (
  <div className="flex flex-col gap-3">
    <search
      aria-label="סינון וחיפוש מועמדויות"
      className={flatSurfaceClasses("flex flex-wrap items-center gap-2 bg-cv-surface px-3 py-2.5")}
    >
      <Field className="w-full sm:w-72 md:min-w-56 md:max-w-2xl md:flex-1" label="חיפוש במועמדויות">
        {(control) => (
          <div className="relative">
            <Search
              aria-hidden="true"
              className="pointer-events-none absolute inset-y-0 start-3 my-auto size-icon-md text-cv-text-muted"
            />
            <Input
              {...control}
              className="ps-9"
              dir="rtl"
              onChange={(event) => onSearchChange(event.target.value)}
              placeholder="חברה או תפקיד"
              type="search"
              value={search}
            />
          </div>
        )}
      </Field>

      <Field className={fieldClasses} label="מועמדויות">
        {(control) => (
          <Select
            {...control}
            onChange={(event) => onActivityChange(event.target.value as ActivityFilter)}
            value={activity}
          >
            {(Object.keys(activityLabels) as ActivityFilter[]).map((key) => (
              <option key={key} value={key}>
                {activityLabels[key]}
              </option>
            ))}
          </Select>
        )}
      </Field>

      <Field className={fieldClasses} label="שלב הכנת קו״ח">
        {(control) => (
          <Select
            {...control}
            onChange={(event) =>
              onPreparationStateChange(event.target.value === "" ? undefined : (event.target.value as PreparationState))
            }
            value={preparationState ?? ""}
          >
            <option value="">כל שלבי הכנת קו״ח</option>
            {/* Keep the selected URL value visible even when its current count is zero. */}
            {(Object.keys(preparationStateLabels) as PreparationState[])
              .filter((stage) => (stageCounts[stage] ?? 0) > 0 || stage === preparationState)
              .map((stage) => (
                <option key={stage} value={stage}>
                  {preparationStateLabels[stage]} ({stageCounts[stage] ?? 0})
                </option>
              ))}
          </Select>
        )}
      </Field>

      <Field className={fieldClasses} label="שלב גיוס">
        {(control) => (
          <Select
            {...control}
            onChange={(event) =>
              onRecruitmentStageChange(event.target.value === "" ? null : (event.target.value as RecruitmentStageId))
            }
            value={recruitmentStage ?? ""}
          >
            <option value="">כל שלבי הגיוס</option>
            {recruitmentStages.map((stage) => (
              <option key={stage.id} value={stage.id}>
                {stage.label} ({recruitmentStageCounts[stage.id] ?? 0})
              </option>
            ))}
          </Select>
        )}
      </Field>
    </search>

    <div className="flex flex-wrap items-center gap-x-4 gap-y-2">
      <p aria-live="polite" className="text-support text-cv-text-muted tabular-nums">
        {resultSummary}
      </p>
      {filtered ? (
        <Button onClick={onClearFilters} size="compact" variant="ghost">
          ניקוי סינון
        </Button>
      ) : null}

      {/* The order is chosen from the table's own headers; there is no separate sort
          control. The cards and stages views keep whichever order the table last set. */}
      <div className="ms-auto">
        <ViewSwitch
          label="בחירת תצוגת מועמדויות"
          onChange={onViewModeChange}
          options={viewModeOptions}
          value={viewMode}
        />
      </div>
    </div>
  </div>
);
