import type { ApplicationListItem, PreparationState } from "@/api/contracts";
import { preparationResumeDestination, preparationStateLabels, reasonTitle } from "@/features/preparation";
import { formatDateTime } from "@/utils/formatDateTime";

export const formatApplicationDate = (value: string): string => formatDateTime(value, "date");

const localDayNumber = (date: Date): number =>
  Math.round(new Date(date.getFullYear(), date.getMonth(), date.getDate()).getTime() / 86_400_000);

/* When an Application last changed, the way the board's card says it after "עודכן": by
   the hour today, by the reader's local calendar day for the rest of the week, then as a
   date. It is presentation only - the full date stays in the element's `dateTime` - and a
   value that does not parse, or one on a later day, falls back to the absolute form
   rather than a guessed phrase. */
export const formatRelativeUpdate = (value: string, now: Date = new Date()): string => {
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) {
    return value;
  }

  const days = localDayNumber(now) - localDayNumber(parsed);
  if (days === 0) {
    const hours = Math.floor((now.getTime() - parsed.getTime()) / 3_600_000);
    return hours < 1 ? "עכשיו" : `לפני ${hours} שע׳`;
  }
  if (days === 1) return "אתמול";
  if (days === 2) return "לפני יומיים";
  if (days > 2 && days < 7) return `לפני ${days} ימים`;
  return `ב־${formatApplicationDate(value)}`;
};

/* Where a CV state sits along the way to Ready, for the card's step bar. The order is the
   one the specification lists the values in (§4) and the one the board's "stage" sort
   already ranks by; it is read from the exhaustive label map rather than restated, so a
   new state cannot be left out of the bar. It is a position, not a promise of forward
   motion: an edit to an approved document projects back to `draft_in_progress`. */
const preparationOrder = Object.keys(preparationStateLabels) as PreparationState[];

export const preparationProgress = (state: PreparationState): { step: number; total: number } => ({
  step: preparationOrder.indexOf(state) + 1,
  total: preparationOrder.length,
});

/* The title of the first reason an Application needs a decision on, or null when nothing
   blocks it. Only review reasons count: a warning disables nothing (§8), and it shows on
   the preparation step it concerns, not as work waiting on the board. The same predicate
   the server's `needs_attention` preset answers. */
export const applicationAttention = (item: ApplicationListItem): string | null => {
  const first = item.review_reasons[0];
  return first === undefined ? null : reasonTitle(first.code, "נדרשת החלטה לפני המשך");
};

export interface HubItem {
  application: ApplicationListItem;
  title: string;
  to: string;
}

/* What blocks the reader across the board, one row per Application, each the way to the
   step that resolves it. A Ready CV is not listed: nothing marks it sent, so it would
   wait in the panel forever. */
export const attentionHubItems = (items: readonly ApplicationListItem[]): HubItem[] =>
  items.flatMap((application) => {
    const title = applicationAttention(application);
    return title === null ? [] : [{ application, title, to: preparationResumeDestination(application) }];
  });
