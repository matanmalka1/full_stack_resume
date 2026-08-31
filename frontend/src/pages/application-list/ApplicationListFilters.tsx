import { Search } from "lucide-react";

import type {
  ActivityFilter,
  ApplicationPreset,
  ApplicationSort,
  PreparationState,
  RecruitmentStatus,
} from "../../api/contracts";
import { Select } from "../../ui/Select";
import { TextInput } from "../../ui/TextInput";
import { cx } from "../../ui/cx";
import {
  applicationPresetLabels,
  preparationStateLabels,
  recruitmentStatusLabel,
  recruitmentStatusOrder,
} from "../applicationLabels";

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

interface PresetChipsProps {
  preset: ApplicationPreset | undefined;
  onPresetChange: (preset: ApplicationPreset | undefined) => void;
}

const PresetChips = ({ preset: active, onPresetChange }: PresetChipsProps) => {
  const chip = (key: string, label: string, selected: boolean, onSelect: () => void) => (
    <label className="cursor-pointer" key={key}>
      <input
        checked={selected}
        className="peer sr-only"
        name="application-preset"
        onChange={onSelect}
        type="radio"
      />
      <span
        className={cx(
          "inline-flex items-center rounded-pill border px-3 py-1.5 text-support font-semibold transition-colors",
          "peer-focus-visible:outline-2 peer-focus-visible:outline-offset-2 peer-focus-visible:outline-cv-focus",
          selected
            ? "border-cv-accent bg-cv-accent-soft text-cv-accent"
            : "border-cv-border bg-cv-surface text-cv-text-muted hover:bg-cv-surface-muted",
        )}
      >
        {label}
      </span>
    </label>
  );

  return (
    <div aria-label="סינון מהיר" className="mt-6 flex flex-wrap items-center gap-2" role="radiogroup">
      {chip("all", "הכל", active === undefined, () => onPresetChange(undefined))}
      {(Object.keys(applicationPresetLabels) as ApplicationPreset[]).map((preset) =>
        chip(preset, applicationPresetLabels[preset], active === preset, () =>
          onPresetChange(preset),
        ),
      )}
    </div>
  );
};

interface ApplicationListFiltersProps {
  activity: ActivityFilter;
  preparationState: PreparationState | undefined;
  preset: ApplicationPreset | undefined;
  recruitmentStatus: RecruitmentStatus | undefined;
  search: string;
  sort: ApplicationSort;
  stageCounts: Partial<Record<PreparationState, number>>;
  onActivityChange: (activity: ActivityFilter) => void;
  onPreparationStateChange: (stage: PreparationState | undefined) => void;
  onPresetChange: (preset: ApplicationPreset | undefined) => void;
  onRecruitmentStatusChange: (status: RecruitmentStatus | undefined) => void;
  onSearchChange: (search: string) => void;
  onSortChange: (sort: ApplicationSort) => void;
}

export const ApplicationListFilters = ({
  activity,
  preparationState,
  preset,
  recruitmentStatus,
  search,
  sort,
  stageCounts,
  onActivityChange,
  onPreparationStateChange,
  onPresetChange,
  onRecruitmentStatusChange,
  onSearchChange,
  onSortChange,
}: ApplicationListFiltersProps) => (
  <>
    <PresetChips onPresetChange={onPresetChange} preset={preset} />

    <div className="mt-3 flex flex-wrap items-end gap-3">
      <div className="min-w-[14rem] flex-1">
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
            onPreparationStateChange(
              event.target.value === "" ? undefined : (event.target.value as PreparationState),
            )
          }
          value={preparationState ?? ""}
        >
          <option value="">הכול</option>
          {(Object.keys(preparationStateLabels) as PreparationState[])
            .filter((stage) => (stageCounts[stage] ?? 0) > 0)
            .map((stage) => (
              <option key={stage} value={stage}>
                {preparationStateLabels[stage]} ({stageCounts[stage]})
              </option>
            ))}
        </Select>
      </div>

      <div>
        <label
          className="block text-support font-semibold text-cv-text"
          htmlFor="list-recruitment-status"
        >
          שלב גיוס
        </label>
        <Select
          className={toolbarControlClasses}
          id="list-recruitment-status"
          onChange={(event) =>
            onRecruitmentStatusChange(
              event.target.value === "" ? undefined : (event.target.value as RecruitmentStatus),
            )
          }
          value={recruitmentStatus ?? ""}
        >
          <option value="">כל שלבי הגיוס</option>
          {recruitmentStatusOrder.map((status) => (
            <option key={status} value={status}>
              {recruitmentStatusLabel(status)}
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
  </>
);
