import type { Classification, ClassificationDecisions } from "@/api/analyses";
import type { ApplicationDetail, Emphasis, Language, ProfileName, Track } from "@/api/contracts";

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

export const matchingSubmission = (current: MatchingValues, next: MatchingValues): ClassificationDecisions => ({
  emphasis_override: current.emphasis === next.emphasis ? null : next.emphasis,
  language_override: current.language === next.language ? null : next.language,
  profile_override: current.profile === next.profile ? null : next.profile,
  track_override: current.track === next.track ? null : next.track,
});

export const changedKeys = (current: MatchingValues, next: MatchingValues): MatchingKey[] =>
  matchingKeys.filter((key) => current[key] !== next[key]);

export const createsAnalysis = (keys: readonly MatchingKey[]): boolean => keys.some((key) => key !== "emphasis");

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
