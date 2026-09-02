import { Search } from "lucide-react";

import type { ActivityFilter, ApplicationSort, PreparationState } from "../../api/contracts";
import { Select } from "../../ui/Select";
import { TextInput } from "../../ui/TextInput";
import { cx } from "../../ui/cx";
import { preparationStateLabels } from "../application/applicationLabels";

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

const toolbarControlClasses = "mt-1 min-h-9 rounded-xl py-1.5";

interface ApplicationListFiltersProps {
  activity: ActivityFilter;
  preparationState: PreparationState | undefined;
  search: string;
  sort: ApplicationSort;
  stageCounts: Partial<Record<PreparationState, number>>;
  onActivityChange: (activity: ActivityFilter) => void;
  onPreparationStateChange: (stage: PreparationState | undefined) => void;
  onSearchChange: (search: string) => void;
  onSortChange: (sort: ApplicationSort) => void;
}

export const ApplicationListFilters = ({
  activity,
  preparationState,
  search,
  sort,
  stageCounts,
  onActivityChange,
  onPreparationStateChange,
  onSearchChange,
  onSortChange,
}: ApplicationListFiltersProps) => (
  /* On a page with no card, the toolbar is what separates the masthead from the board,
     so it closes with the same hairline the masthead opens with rather than floating
     between two unrelated blocks. */
  <div className="border-b border-cv-border pb-5">
    <div className="flex flex-wrap items-end gap-3">
      {/* The search field is capped rather than elastic: at board width `flex-1` gave it
          several times the width of the selects beside it, and a field that wide reads
          as the page's subject instead of one control among the toolbar filters. */}
      <div className="min-w-[14rem] max-w-sm flex-1">
        <label className="block text-support font-semibold text-cv-text" htmlFor="list-search">
          חיפוש
        </label>
        <div className="relative mt-1">
          <Search
            aria-hidden="true"
            className="pointer-events-none absolute inset-y-0 start-3 my-auto size-4 text-cv-text-muted"
          />
          <TextInput
            className={cx(toolbarControlClasses, "ps-8")}
            dir="rtl"
            id="list-search"
            onChange={(event) => onSearchChange(event.target.value)}
            placeholder="חברה או תפקיד"
            type="search"
            value={search}
          />
        </div>
      </div>

      <div>
        <label className="block text-support font-semibold text-cv-text" htmlFor="list-activity">
          מועמדויות
        </label>
        <Select
          className={toolbarControlClasses}
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
        <label className="block text-support font-semibold text-cv-text" htmlFor="list-stage">
          מצב קורות החיים
        </label>
        <Select
          className={toolbarControlClasses}
          id="list-stage"
          onChange={(event) =>
            onPreparationStateChange(event.target.value === "" ? undefined : (event.target.value as PreparationState))
          }
          value={preparationState ?? ""}
        >
          <option value="">הכול</option>
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
        <label className="block text-support font-semibold text-cv-text" htmlFor="list-sort">
          סדר
        </label>
        <Select
          className={toolbarControlClasses}
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
      </div>
    </div>
  </div>
);
