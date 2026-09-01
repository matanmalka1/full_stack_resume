import type { ApplicationListQuery } from "../api/applications";
import type {
  ActivityFilter,
  ApplicationPreset,
  ApplicationSort,
  PreparationState,
  RecruitmentStatus,
} from "../api/contracts";

/* The list query as it lives in the address bar.

   The board's state belongs in the URL rather than in component state: a filtered board
   is a thing a user comes back to, links to, and reloads, and none of that survives state
   that only exists while the component is mounted. It is also the browser's own back
   button - narrowing and then going back is the gesture people already know.

   The parameter names are the API's, so what is in the address bar is the question that
   was asked. It is deliberately not passed through to `fetch` as an opaque string: an
   arbitrary value in the URL must not become an arbitrary request, so every field is read
   back through the closed sets below and anything unrecognised falls to the default. */

const PAGE_SIZE = 25;

/* Exhaustive over the generated unions rather than a list written a second time: a filter
   or ordering added to the backend fails the build here instead of being silently dropped
   from a URL it is valid in. The values are unused - only the keys are read. */
const activityFilters: Record<ActivityFilter, true> = { open: true, closed: true, all: true };

const sorts: Record<ApplicationSort, true> = {
  updated: true,
  created: true,
  company: true,
  stage: true,
};

const preparationStates: Record<PreparationState, true> = {
  needs_analysis: true,
  needs_review: true,
  ready_to_draft: true,
  draft_in_progress: true,
  ready_for_approval: true,
  approved: true,
  ready: true,
};

/* The recruitment axis, exhaustive over the generated union for the same reason as the
   tables above: a status added to the domain fails the build here rather than being
   silently dropped from a URL it is valid in. */
const recruitmentStatuses: Record<RecruitmentStatus, true> = {
  saved: true,
  applied: true,
  recruiter_screen: true,
  interview: true,
  assignment: true,
  final_stage: true,
  offer: true,
  accepted: true,
  rejected: true,
  withdrawn: true,
  closed: true,
};

const presets: Record<ApplicationPreset, true> = {
  needs_attention: true,
  ready_to_send: true,
  active_interviews: true,
};

const known = <T extends string>(table: Record<T, true>, value: string | null): T | undefined =>
  value !== null && Object.hasOwn(table, value) ? (value as T) : undefined;

/* A page number that is not a whole number of pages is not a page. `Number.parseInt`
   would read "3abc" as 3 and "1e9" as 1, so the digits are checked before the parse. */
const wholeNumber = (value: string | null): number | undefined => {
  if (value === null || !/^\d+$/.test(value)) {
    return undefined;
  }
  const parsed = Number(value);
  return Number.isSafeInteger(parsed) ? parsed : undefined;
};

/* The board opens on live work: a finished process stays stored and reachable through the
   filter, but it is not what the screen is asking about. */
const defaultActivity: ActivityFilter = "open";

export const queryFromParams = (params: URLSearchParams): ApplicationListQuery => {
  const stages = params.getAll("stage").flatMap((stage) => {
    const match = known(preparationStates, stage);
    return match === undefined ? [] : [match];
  });
  const statuses = params.getAll("recruitment_status").flatMap((status) => {
    const match = known(recruitmentStatuses, status);
    return match === undefined ? [] : [match];
  });
  const preset = known(presets, params.get("preset"));
  const search = params.get("search") ?? "";
  /* Rounded down to a page boundary. An offset the pager could never have produced would
     leave its "previous" button one partial page from the start. */
  const offset =
    Math.floor((wholeNumber(params.get("offset")) ?? 0) / PAGE_SIZE) * PAGE_SIZE;

  return {
    activity: known(activityFilters, params.get("activity")) ?? defaultActivity,
    sort: known(sorts, params.get("sort")) ?? "updated",
    limit: PAGE_SIZE,
    ...(stages.length === 0 ? {} : { stages }),
    ...(statuses.length === 0 ? {} : { recruitmentStatuses: statuses }),
    ...(preset === undefined ? {} : { preset }),
    ...(search === "" ? {} : { search }),
    ...(offset === 0 ? {} : { offset }),
  };
};

/* Only what differs from the default is written, so the address bar of an untouched board
   stays clean and a shared link carries exactly the narrowing its sender applied.

   `limit` is absent on purpose: the page size is this screen's layout decision rather than
   part of the question, and a user editing it in the URL would be setting a bound the
   screen has no control for. */
export const paramsFromQuery = (query: ApplicationListQuery): URLSearchParams => {
  const params = new URLSearchParams();

  if (query.activity !== undefined && query.activity !== defaultActivity) {
    params.set("activity", query.activity);
  }
  for (const stage of query.stages ?? []) {
    params.append("stage", stage);
  }
  for (const status of query.recruitmentStatuses ?? []) {
    params.append("recruitment_status", status);
  }
  if (query.preset !== undefined) {
    params.set("preset", query.preset);
  }
  if (query.search !== undefined && query.search !== "") {
    params.set("search", query.search);
  }
  if (query.sort !== undefined && query.sort !== "updated") {
    params.set("sort", query.sort);
  }
  if (query.offset !== undefined && query.offset !== 0) {
    params.set("offset", String(query.offset));
  }

  return params;
};

export { PAGE_SIZE };
