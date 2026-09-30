import { ChevronDown } from "lucide-react";
import { useId, useState } from "react";

import type { ActivityFilter, ApplicationSort, PreparationState } from "@/api/contracts";
import { preparationStateLabels } from "@/features/preparation";
import { Button } from "@/ui/Button";
import { cx } from "@/ui/cx";
import { Field } from "@/ui/Field";
import { SearchInput } from "@/ui/Input";
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

/* Exhaustive over the generated union, so an order added to the list endpoint fails the
   build here rather than being missing from the menu. Each order has one direction on
   the server, and the label says which. */
const sortLabels: Record<ApplicationSort, string> = {
  updated: "עדכון אחרון",
  created: "נוצרו לאחרונה",
  company: "שם החברה",
  stage: "התקדמות ההכנה",
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
}: ApplicationListToolbarProps) => {
  const filtersId = useId();
  const [filtersOpen, setFiltersOpen] = useState(false);
  const activeFilters =
    (activity === "open" ? 0 : 1) + (preparationState === undefined ? 0 : 1) + (recruitmentStage === null ? 0 : 1);

  return (
    <div className="flex flex-col gap-3">
      <search
        aria-label="סינון וחיפוש מועמדויות"
        className={flatSurfaceClasses(
          "cv-fields-compact flex flex-wrap items-center gap-2 rounded-control bg-cv-surface px-3 py-2.5",
        )}
      >
        <Field className="w-full sm:w-72 md:min-w-56 md:max-w-2xl md:flex-1" label="חיפוש במועמדויות">
          {(control) => (
            <SearchInput
              {...control}
              dir="rtl"
              onChange={(event) => onSearchChange(event.target.value)}
              placeholder="חברה או תפקיד"
              value={search}
            />
          )}
        </Field>

        {/* On a phone the three selects fold behind one control. Open, they stacked four
          full-width fields between the board's title and its first card, so the card the
          reader came back to started at the bottom of the screen. Only their visibility
          folds: the filters themselves live in the address as before, and the count on
          the control says when any is narrowing the board. From `sm` they sit in the row
          as they always did. */}
        <Button
          aria-controls={filtersId}
          aria-expanded={filtersOpen}
          className="w-full justify-between sm:hidden"
          onClick={() => setFiltersOpen((open) => !open)}
          size="default"
          variant="secondary"
        >
          <span>{activeFilters === 0 ? "סינון" : `סינון · ${activeFilters} פעילים`}</span>
          <ChevronDown
            aria-hidden="true"
            className={cx("size-icon-md transition-transform", filtersOpen && "rotate-180")}
          />
        </Button>

        <div className={cx(filtersOpen ? "flex w-full flex-col gap-2" : "hidden", "sm:contents")} id={filtersId}>
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
                  onPreparationStateChange(
                    event.target.value === "" ? undefined : (event.target.value as PreparationState),
                  )
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
                  onRecruitmentStageChange(
                    event.target.value === "" ? null : (event.target.value as RecruitmentStageId),
                  )
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
        </div>
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

        {/* Sorting orders the page rather than narrowing it, so it sits beside the view
          switch rather than among the filters, and every view keeps the order it sets. */}
        <div className="cv-fields-compact ms-auto flex flex-wrap items-center gap-3">
          <label className="flex items-center gap-2 text-support text-cv-text-muted">
            מיון
            <Select
              className="w-auto"
              onChange={(event) => onSortChange(event.target.value as ApplicationSort)}
              value={sort}
            >
              {(Object.keys(sortLabels) as ApplicationSort[]).map((key) => (
                <option key={key} value={key}>
                  {sortLabels[key]}
                </option>
              ))}
            </Select>
          </label>
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
};
