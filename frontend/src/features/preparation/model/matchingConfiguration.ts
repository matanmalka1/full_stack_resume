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

/* What saving does to the document, per §13: a classification change creates a new
   analysis and leaves the document where it is (it then carries
   `DOCUMENT_ON_OLDER_ANALYSIS` until the user rebuilds it); an Emphasis-only change
   updates the document's own selection in place. */
export const matchingConsequence = (detail: ApplicationDetail, newAnalysis: boolean): string => {
  const hasDocument = detail.document_id != null;
  const hasContent =
    hasDocument && detail.preparation_state !== "needs_analysis" && detail.preparation_state !== "ready_to_draft";
  if (newAnalysis) {
    return hasDocument
      ? "השמירה תיצור ניתוח חדש. המסמך יישאר בנוי על הניתוח הנוכחי עד שתבחרו לבנות אותו מחדש מהניתוח החדש."
      : "השמירה תיצור ניתוח חדש. הקודם נשמר בהיסטוריה.";
  }
  return hasContent
    ? "השמירה תעדכן את בחירת העובדות של המסמך, וייתכן שגם את תוכן הטיוטה. אישור קיים לא יחול עוד על המסמך שהשתנה."
    : "השמירה תעדכן את בחירת העובדות של המסמך, בלי להחליף את הניתוח.";
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
