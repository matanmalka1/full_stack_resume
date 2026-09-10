import { Search } from "lucide-react";

import type { ActivityFilter, ApplicationSort, PreparationState } from "@/api/contracts";
import { preparationStateLabels } from "@/features/preparation";
import { Button } from "@/ui/Button";
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

const sortLabels: Record<ApplicationSort, string> = {
  updated: "עודכן לאחרונה",
  created: "נוצר לאחרונה",
  company: "לפי חברה",
  stage: "לפי מצב קורות החיים",
};

/* Sized by the longest option rather than by a shared fixed width: "כל מצבי קורות
   החיים" is a good deal longer than "פעילות", and one width for both either clipped
   that label under the native arrow or padded the short menu out with empty space.
   The bounds keep the row from turning ragged - nothing narrower than a real target,
   nothing wide enough to push the rest of the bar off the line. */
const fieldClasses = "w-full min-w-0 sm:w-auto sm:min-w-36 sm:max-w-64";

interface ApplicationListToolbarProps {
  activity: ActivityFilter;
  filtered: boolean;
  preparationState: PreparationState | undefined;
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
  onRecruitmentStageChange: (stage: RecruitmentStageId | null) => void;
  onSearchChange: (search: string) => void;
  onSortChange: (sort: ApplicationSort) => void;
  onViewModeChange: (view: ViewMode) => void;
}

/* Everything that narrows the board and everything that decides how it is drawn, in
   one bar. The named slices moved up beside the page title, where the reader picks a
   slice before asking anything else; what is left here is one row - the question on
   the reading side, the presentation controls pushed to the far end - inside a single
   surface, so the controls read as one object above the board rather than as loose
   fields on the page's ground.

   A control that is set says so by showing its own value, so nothing is restated as a
   removable chip: one control, one place, plus a single way to put every filter back to
   its default. Sort survives that reset, because it orders the list rather than
   narrowing it. The count of what matched sits under the bar, next to that reset. */
export const ApplicationListToolbar = ({
  activity,
  filtered,
  preparationState,
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
  onRecruitmentStageChange,
  onSearchChange,
  onSortChange,
  onViewModeChange,
}: ApplicationListToolbarProps) => (
  <div className="flex flex-col gap-3">
    <search
      aria-label="סינון וחיפוש מועמדויות"
      className={flatSurfaceClasses("flex flex-wrap items-center gap-2 bg-cv-surface px-3 py-2.5")}
    >
      <label className="sr-only" htmlFor="list-search">
        חיפוש במועמדויות
      </label>
      {/* The question grows into whatever the filters leave: the four controls are sized
          by their own labels, so on a wide board they used to sit against the reading
          edge with the rest of the surface empty beside them. */}
      <div className="relative w-full sm:w-72 md:min-w-56 md:max-w-2xl md:flex-1">
        <Search
          aria-hidden="true"
          className="pointer-events-none absolute inset-y-0 start-3 my-auto size-icon-md text-cv-text-muted"
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

    </search>

    {/* What matched, and how it is drawn, on one line under the bar. The presentation
        controls used to sit inside the filter surface behind `ms-auto`, which held on a
        very wide window and broke everywhere else: below about 1500px the group wrapped
        to a second line of its own and left most of that line empty, so the bar drew a
        blank band across the page. Reading the count and choosing the view are also two
        different questions from narrowing the board, and the row they now share has no
        width at which it goes ragged. */}
    <div className="flex flex-wrap items-center gap-x-4 gap-y-2">
      <p aria-live="polite" className="text-support text-cv-text-muted tabular-nums">
        {resultSummary}
      </p>
      {filtered ? (
        <Button onClick={onClearFilters} size="compact" variant="ghost">
          ניקוי סינון
        </Button>
      ) : null}

      <div className="flex items-center gap-2 ms-auto">
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
  </div>
);
