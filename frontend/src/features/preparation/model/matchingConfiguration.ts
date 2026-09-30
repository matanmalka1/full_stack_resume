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

/* What saving does to the document, per §13: every decision - Emphasis included - creates
   a new analysis and leaves the document where it is (it then carries
   `DOCUMENT_ON_OLDER_ANALYSIS` until the user rebuilds it). */
export const matchingConsequence = (detail: ApplicationDetail): string =>
  detail.document_id != null
    ? "השמירה תיצור ניתוח חדש. המסמך יישאר בנוי על הניתוח הנוכחי עד שתבחרו לבנות אותו מחדש מהניתוח החדש."
    : "השמירה תיצור ניתוח חדש. הקודם נשמר בהיסטוריה.";

type MatchingOrigin = "analysis" | "decided";

export const matchingOrigin = (key: MatchingKey, classification: Classification): MatchingOrigin =>
  classification.decided.includes(key) ? "decided" : "analysis";
