import type { ApplicationListItem, PreparationState } from "@/api/contracts";
import { preparationStateLabels, reasonTitle } from "@/features/preparation";

/* Where a CV state sits along the way to Ready, for the step bar. The order is the one
   the specification lists the values in (§4); it is read from the exhaustive label map
   rather than restated, so a new state cannot be left out of the bar. It is a position,
   not a promise of forward motion: an edit to an approved document projects back to
   `draft_in_progress`. */
const preparationOrder = Object.keys(preparationStateLabels) as PreparationState[];

export const preparationProgress = (state: PreparationState): { step: number; total: number } => ({
  step: preparationOrder.indexOf(state) + 1,
  total: preparationOrder.length,
});

/* The title of the first reason an Application needs a decision on, or null when nothing
   blocks it. Only review reasons count: a warning disables nothing (§8), and it shows on
   the preparation step it concerns. The same predicate the server's `needs_attention`
   preset answers. */
export const applicationAttention = (item: ApplicationListItem): string | null => {
  const first = item.review_reasons[0];
  return first === undefined ? null : reasonTitle(first.code, "נדרשת החלטה לפני המשך");
};
