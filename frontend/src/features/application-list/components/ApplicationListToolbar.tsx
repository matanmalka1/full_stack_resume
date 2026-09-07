import { Search } from "lucide-react";

import type { ActivityFilter, ApplicationSort, PreparationState } from "@/api/contracts";
import { preparationStateLabels } from "@/features/preparation";
import { Button } from "@/ui/Button";
import { Input } from "@/ui/Input";
import { Select } from "@/ui/Select";
import { ViewSwitch } from "@/ui/ViewSwitch";
import { type ViewMode, viewModeOptions } from "../model/applicationViews";
import { type RecruitmentStageId, recruitmentStages } from "../model/recruitmentStages";
import { ApplicationPresetTabs, type PresetSelection } from "./ApplicationPresetTabs";

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

const fieldClasses = "w-full min-w-0 sm:w-44";

interface ApplicationListToolbarProps {
  activity: ActivityFilter;
  filtered: boolean;
  preparationState: PreparationState | undefined;
  preset: PresetSelection;
  presetCounts: Record<string, number> | undefined;
  recruitmentStage: RecruitmentStageId | null;
  recruitmentStageCounts: Partial<Record<RecruitmentStageId, number>>;
  resultSummary: string;
  search: string;
  sort: ApplicationSort;
  stageCounts: Partial<Record<PreparationState, number>>;
  viewMode: ViewMode;
  onActivityChange: (activity: ActivityFilter) => void;
  onClearFilters: () => void;
  onPreparationStateChange: (stage: PreparationState | undefined) => void;
  onPresetSelect: (preset: PresetSelection) => void;
  onRecruitmentStageChange: (stage: RecruitmentStageId | null) => void;
  onSearchChange: (search: string) => void;
  onSortChange: (sort: ApplicationSort) => void;
  onViewModeChange: (view: ViewMode) => void;
}

/* Everything that decides which Applications are on screen and how they are drawn, in
   one band, on the page's own ground rather than inside a surface of its own. A card
   here would be the third border above the board and would read as content; these are
   controls for the content below them.
   
   The two rows are two different questions. The first is which slice, and how it is
   presented - the answer the reader changes often and reads at a glance. The second is
   how that slice is narrowed, and what it currently matches.
   
   A control that is set says so by showing its own value, so nothing is restated as a
   removable chip underneath: one control, one place, plus a single way to put every
   filter back to its default. Sort survives that reset, because it orders the list
   rather than narrowing it. */
export const ApplicationListToolbar = ({
  activity,
  filtered,
  preparationState,
  preset,
  presetCounts,
  recruitmentStage,
  recruitmentStageCounts,
  resultSummary,
  search,
  sort,
  stageCounts,
  viewMode,
  onActivityChange,
  onClearFilters,
  onPreparationStateChange,
  onPresetSelect,
  onRecruitmentStageChange,
  onSearchChange,
  onSortChange,
  onViewModeChange,
}: ApplicationListToolbarProps) => (
  <div className="flex flex-col gap-3">
    <div className="flex flex-wrap items-center justify-between gap-x-4 gap-y-2">
      <ApplicationPresetTabs counts={presetCounts} onSelect={onPresetSelect} value={preset} />

      <div className="flex items-center gap-2">
        <label className="sr-only" htmlFor="list-sort">
          סדר
        </label>
        <Select
          className="w-40"
          id="list-sort"
          onChange={(event) => onSortChange(event.target.value as ApplicationSort)}
          value={sort}
        >
          {(Object.keys(sortLabels) as ApplicationSort[]).map((key) => (
            <option key={key} value={key}>
              {sortLabels[key]}
            </option>
          ))}
        </Select>
        <ViewSwitch
          label="בחירת תצוגת מועמדויות"
          onChange={onViewModeChange}
          options={viewModeOptions}
          value={viewMode}
        />
      </div>
    </div>

    <div
      aria-label="סינון וחיפוש מועמדויות"
      className="flex flex-wrap items-center gap-2 border-t border-cv-border pt-3"
      role="search"
    >
      <label className="sr-only" htmlFor="list-search">
        חיפוש במועמדויות
      </label>
      <div className="relative w-full sm:w-72">
        <Search
          aria-hidden="true"
          className="pointer-events-none absolute inset-y-0 start-3 my-auto size-4 text-cv-text-muted"
        />
        <Input
          className="ps-9"
          dir="rtl"
          id="list-search"
          onChange={(event) => onSearchChange(event.target.value)}
          placeholder="חברה או תפקיד"
          type="search"
          value={search}
        />
      </div>

      <label className="sr-only" htmlFor="list-activity">
        מועמדויות
      </label>
      <Select
        className={fieldClasses}
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

      <label className="sr-only" htmlFor="list-stage">
        מצב קורות החיים
      </label>
      <Select
        className={fieldClasses}
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

      <label className="sr-only" htmlFor="list-recruitment-stage">
        שלב גיוס
      </label>
      <Select
        className={fieldClasses}
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

      <div className="flex items-center gap-2 sm:ms-auto">
        <p aria-live="polite" className="text-support text-cv-text-muted tabular-nums">
          {resultSummary}
        </p>
        {filtered ? (
          <Button onClick={onClearFilters} size="compact" variant="ghost">
            ניקוי סינון
          </Button>
        ) : null}
      </div>
    </div>
  </div>
);
