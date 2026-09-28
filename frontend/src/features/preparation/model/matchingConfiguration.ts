import type { Classification, ClassificationDecisions } from "@/api/analyses";
import type { ApplicationDetail, Emphasis, Language, ProfileName, Track } from "@/api/contracts";

/* The four values the analysis and the fact selection are built from, as one form. */
export interface MatchingValues {
  emphasis: Emphasis;
  language: Language;
  profile: ProfileName;
  track: Track;
}

export type MatchingKey = keyof MatchingValues;

export const matchingKeys: readonly MatchingKey[] = ["track", "profile", "emphasis", "language"];

export const matchingValuesFrom = (classification: Classification): MatchingValues | null =>
  classification.track === null ||
  classification.profile === null ||
  classification.emphasis === null ||
  classification.language === null
    ? null
    : {
        emphasis: classification.emphasis,
        language: classification.language,
        profile: classification.profile,
        track: classification.track,
      };

/* Only what the reader changed is submitted: the application layer merges a submission
   over the overrides already recorded, so an unchanged value is an absent field. */
export const matchingSubmission = (current: MatchingValues, next: MatchingValues): ClassificationDecisions => ({
  emphasis_override: current.emphasis === next.emphasis ? null : next.emphasis,
  language_override: current.language === next.language ? null : next.language,
  profile_override: current.profile === next.profile ? null : next.profile,
  track_override: current.track === next.track ? null : next.track,
});

export const changedKeys = (current: MatchingValues, next: MatchingValues): MatchingKey[] =>
  matchingKeys.filter((key) => current[key] !== next[key]);

/* Emphasis is effective at SelectionPlan level, so changing it alone rebuilds only the
   selection. Track, profile and language are part of the analysis itself and produce a
   new one. */
export const createsAnalysis = (keys: readonly MatchingKey[]): boolean => keys.some((key) => key !== "emphasis");

/* What a save will do to the work already done, from the server's own state. */
export const matchingConsequence = (detail: ApplicationDetail, newAnalysis: boolean): string => {
  const replacement = newAnalysis ? "ניתוח ובחירת עובדות חדשים" : "בחירת עובדות חדשה, בלי להחליף את הניתוח";
  if (detail.active_working_draft_id != null) {
    return `השמירה תיצור ${replacement}. הטיוטה הפעילה לא תימחק, אך לא תתאים להגדרות החדשות, ויהיה צריך להחליף אותה לפני האישור.`;
  }
  if (detail.latest_approved_revision_id != null || detail.latest_ready_revision_id != null) {
    return `השמירה תיצור ${replacement}. הגרסאות שאושרו והקבצים המוכנים לא ישתנו ויישארו זמינים בהיסטוריה; העבודה תמשיך מההגדרות החדשות.`;
  }
  return `השמירה תיצור ${replacement}. הקודמים נשמרים בהיסטוריה.`;
};

/* Where a value on the form came from: the analysis proposed it, or the reader decided
   it on an earlier save. The analysis document keeps its own original emphasis, so an
   effective emphasis that differs from it was decided even when no override key says
   so on the analysis. */
type MatchingOrigin = "analysis" | "decided";

export const matchingOrigin = (
  key: MatchingKey,
  classification: Classification,
  detail: ApplicationDetail,
): MatchingOrigin => {
  if (classification.decided.includes(key)) {
    return "decided";
  }
  if (key === "emphasis") {
    const proposed = detail.latest_analysis?.analysis.emphasis;
    return typeof proposed === "string" && proposed !== classification.emphasis ? "decided" : "analysis";
  }
  return "analysis";
};
