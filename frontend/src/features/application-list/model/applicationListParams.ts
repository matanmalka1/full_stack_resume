import type { ApplicationListQuery } from "@/api/applications";
import type { ApplicationPreset, ApplicationSort } from "@/api/contracts";

/* The list query as it lives in the address bar.

   The board's state belongs in the URL rather than in component state: a narrowed board
   is a thing a user comes back to, links to, and reloads, and none of that survives state
   that only exists while the component is mounted. It is also the browser's own back
   button - narrowing and then going back is the gesture people already know.

   The board asks two things of the reader: which named slice (`preset`) and in what
   order (`sort`). There is no search box, stage menu or pager here and nothing of
   theirs in the URL.

   The parameter names are the API's, so what is in the address bar is the question that
   was asked. It is deliberately not passed through to `fetch` as an opaque string: an
   arbitrary value in the URL must not become an arbitrary request, so every field is read
   back through the closed sets below and anything unrecognised falls to the default. */

/* The board draws every Application at once - the design has no pager - so it asks
   for the endpoint's largest page. A board past it is far beyond the product's scale; the
   cut is the server's own bound rather than a second one invented here. */
export const BOARD_LIMIT = 200;

/* Exhaustive over the generated unions rather than a list written a second time: an
   ordering or preset added to the backend fails the build here instead of being silently
   dropped from a URL it is valid in. The values are unused - only the keys are read. */
const sorts: Record<ApplicationSort, true> = {
  updated: true,
  created: true,
  company: true,
  stage: true,
};

const presets: Record<ApplicationPreset, true> = {
  needs_attention: true,
  ready_to_send: true,
};

const known = <T extends string>(table: Record<T, true>, value: string | null): T | undefined =>
  value !== null && Object.hasOwn(table, value) ? (value as T) : undefined;

export const queryFromParams = (params: URLSearchParams): ApplicationListQuery => {
  const preset = known(presets, params.get("preset"));

  return {
    sort: known(sorts, params.get("sort")) ?? "updated",
    limit: BOARD_LIMIT,
    ...(preset === undefined ? {} : { preset }),
  };
};

/* Only what differs from the default is written, so the address bar of an untouched board
   stays clean and a shared link carries exactly the narrowing its sender applied. */
export const paramsFromQuery = (query: ApplicationListQuery): URLSearchParams => {
  const params = new URLSearchParams();

  if (query.preset !== undefined) {
    params.set("preset", query.preset);
  }
  if (query.sort !== undefined && query.sort !== "updated") {
    params.set("sort", query.sort);
  }

  return params;
};
