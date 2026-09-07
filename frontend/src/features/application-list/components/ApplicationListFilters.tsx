import { Search } from "lucide-react";
import type { ReactNode } from "react";

import type { ActivityFilter, ApplicationPreset, ApplicationSort, PreparationState } from "@/api/contracts";
import { Select } from "@/ui/Select";
import { Input } from "@/ui/Input";
import { preparationStateLabels } from "@/features/preparation";
import { type RecruitmentStageId, recruitmentStages } from "../model/recruitmentStages";
import { ApplicationActiveFilters } from "./ApplicationActiveFilters";

const activityLabels: Record<ActivityFilter, string> = {
  open: "פעילות",
  closed: "סגורות",
  all: "הכול",
};

const sortLabels: Record<ApplicationSort, string> = {
  updated: "עודכן לאחרונה",
  created: "נוצר לאחרונה",
  company: "לפי חברה",
  stage: "לפי מצב קורות החיים",
};

interface ApplicationListFiltersProps {
  activity: ActivityFilter;
  activePreset: ApplicationPreset | undefined;
  preparationState: PreparationState | undefined;
  recruitmentStage: RecruitmentStageId | null;
  recruitmentStageCounts: Partial<Record<RecruitmentStageId, number>>;
  resultSummary: ReactNode;
  search: string;
  sort: ApplicationSort;
  stageCounts: Partial<Record<PreparationState, number>>;
  viewSwitch: ReactNode;
  onActivityChange: (activity: ActivityFilter) => void;
  onClearAll: () => void;
  onPresetClear: () => void;
  onPreparationStateChange: (stage: PreparationState | undefined) => void;
  onRecruitmentStageChange: (stage: RecruitmentStageId | null) => void;
  onSearchChange: (search: string) => void;
  onSortChange: (sort: ApplicationSort) => void;
}

export const ApplicationListFilters = ({
  activity,
  activePreset,
  preparationState,
  recruitmentStage,
  recruitmentStageCounts,
  resultSummary,
  search,
  sort,
  stageCounts,
  viewSwitch,
  onActivityChange,
  onClearAll,
  onPresetClear,
  onPreparationStateChange,
  onRecruitmentStageChange,
  onSearchChange,
  onSortChange,
}: ApplicationListFiltersProps) => {
  return (
    <div
      aria-label="סינון וחיפוש מועמדויות"
      className="rounded-surface border border-cv-border bg-cv-surface p-3"
      role="search"
    >
      <div className="mb-3 flex flex-wrap items-center justify-between gap-3">
        <p aria-live="polite" className="text-support font-semibold text-cv-text-muted">
          {resultSummary}
        </p>
        {viewSwitch}
      </div>
      <div className="grid grid-cols-1 items-end gap-2 sm:grid-cols-2 xl:grid-cols-6">
        <div className="min-w-0 xl:col-span-2">
          <label className="sr-only" htmlFor="list-search">
            חיפוש במועמדויות
          </label>
          <div className="relative">
            <Search
              aria-hidden="true"
              className="pointer-events-none absolute inset-y-0 start-3 my-auto size-4 text-cv-text-muted"
            />
            <Input
              className="ps-8"
              dir="rtl"
              id="list-search"
              onChange={(event) => onSearchChange(event.target.value)}
              placeholder="חיפוש במועמדויות לפי חברה או תפקיד"
              type="search"
              value={search}
            />
          </div>
        </div>

        <div className="xl:col-start-3">
          <label className="sr-only" htmlFor="list-activity">
            מועמדויות
          </label>
          <Select
            id="list-activity"
            onChange={(event) => onActivityChange(event.target.value as ActivityFilter)}
            value={activity}
          >
            {(Object.keys(activityLabels) as ActivityFilter[]).map((key) => (
              <option key={key} value={key}>
                {activityLabels[key]}
              </option>
            ))}
          </Select>
        </div>

        <div>
          <label className="sr-only" htmlFor="list-stage">
            מצב קורות החיים
          </label>
          <Select
            id="list-stage"
            onChange={(event) =>
              onPreparationStateChange(event.target.value === "" ? undefined : (event.target.value as PreparationState))
            }
            value={preparationState ?? ""}
          >
            <option value="">כל מצבי קורות החיים</option>
            {/* The menu hides stages nothing is in, except the one the URL already selects:
              dropping that option left the select falling back to its first - "הכול" -
              while the filter was in fact still applied, so the control disagreed with
              the results it produced. */}
            {(Object.keys(preparationStateLabels) as PreparationState[])
              .filter((stage) => (stageCounts[stage] ?? 0) > 0 || stage === preparationState)
              .map((stage) => (
                <option key={stage} value={stage}>
                  {preparationStateLabels[stage]} ({stageCounts[stage] ?? 0})
                </option>
              ))}
          </Select>
        </div>

        <div>
          <label className="sr-only" htmlFor="list-recruitment-stage">
            שלב גיוס
          </label>
          <Select
            id="list-recruitment-stage"
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
        </div>

        <div>
          <label className="sr-only" htmlFor="list-sort">
            סדר
          </label>
          <Select id="list-sort" onChange={(event) => onSortChange(event.target.value as ApplicationSort)} value={sort}>
            {(Object.keys(sortLabels) as ApplicationSort[]).map((key) => (
              <option key={key} value={key}>
                {sortLabels[key]}
              </option>
            ))}
          </Select>
        </div>
      </div>
      <ApplicationActiveFilters
        activePreset={activePreset}
        activity={activity}
        onActivityChange={onActivityChange}
        onClearAll={onClearAll}
        onPreparationStateChange={onPreparationStateChange}
        onPresetClear={onPresetClear}
        onRecruitmentStageChange={onRecruitmentStageChange}
        onSearchChange={onSearchChange}
        onSortChange={onSortChange}
        preparationState={preparationState}
        recruitmentStage={recruitmentStage}
        search={search}
        sort={sort}
      />
    </div>
  );
};
