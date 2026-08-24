import { type ApiPath, apiRequest } from "./client";
import type {
  AnalysisDecisions,
  ApplicationDetail,
  ApplyAnalysisDecisionsRequest,
  Emphasis,
  Language,
  ProfileName,
  Track,
} from "./contracts";
import {
  type FitLevel,
  emphasisLabels,
  fitLabels,
  languageLabels,
  profileLabels,
  trackLabels,
} from "../pages/analysisLabels";

/* The four classification decisions this screen may submit. The fact overlay is
   deliberately absent: no endpoint exposes the candidate fact pool to the browser, and
   the backend refuses a submission carrying both kinds at once. Omitting the fields
   makes that refusal unreachable from here by construction rather than by a client-side
   copy of a server rule. */
export type ClassificationDecisions = Pick<
  ApplyAnalysisDecisionsRequest,
  "track_override" | "profile_override" | "emphasis_override" | "language_override" | "accept_low_fit"
>;

const applyDecisionsPath = (analysisId: string): ApiPath =>
  `/api/v1/analyses/${encodeURIComponent(analysisId)}/apply-decisions`;

/* §13: synchronous, one commit, no Operation - so no `Idempotency-Key` and no
   `202`/`Location` obligation. `application_id` is stated rather than inferred from the
   analysis: a client that names both is telling the server what it believes, and a
   mismatch is a `412` naming the broken lineage instead of a decision landing on
   another Application's analysis.

   Only the decisions that were actually set are sent. A blank control is an absent
   field, not an empty string, because the application layer merges a submission over
   the overrides already recorded: withholding a field keeps what was decided before,
   and sending `""` would be a value that settles nothing. */
export const applyAnalysisDecisions = async (
  analysisId: string,
  applicationId: string,
  decisions: ClassificationDecisions,
): Promise<AnalysisDecisions> => {
  /* The overlay fields are omitted by type, not merely left unset: naming them in the
     `Omit` is what makes adding one here a compile error rather than a quiet change of
     what this screen commits. */
  const body: Omit<ApplyAnalysisDecisionsRequest, "pinned_fact_ids" | "excluded_fact_ids"> = {
    application_id: applicationId,
    accept_low_fit: decisions.accept_low_fit,
    ...(decisions.track_override == null ? {} : { track_override: decisions.track_override }),
    ...(decisions.profile_override == null ? {} : { profile_override: decisions.profile_override }),
    ...(decisions.emphasis_override == null
      ? {}
      : { emphasis_override: decisions.emphasis_override }),
    ...(decisions.language_override == null
      ? {}
      : { language_override: decisions.language_override }),
  };

  const response = await apiRequest<AnalysisDecisions>(applyDecisionsPath(analysisId), {
    method: "POST",
    body,
  });
  return response.data;
};

/* Membership checks derived from the exhaustive Hebrew maps rather than written a
   second time: a value the backend adds fails the build at the map, and a value this
   build does not recognize is reported as absent instead of rendering `undefined`. */
const memberOf =
  <T extends string>(labels: Record<T, string>) =>
  (value: unknown): value is T =>
    typeof value === "string" && Object.hasOwn(labels, value);

const isTrack = memberOf<Track>(trackLabels);
const isProfileName = memberOf<ProfileName>(profileLabels);
const isEmphasis = memberOf<Emphasis>(emphasisLabels);
const isLanguage = memberOf<Language>(languageLabels);
const isFitLevel = memberOf<FitLevel>(fitLabels);

export interface AnalysisGap {
  requirement: string;
  severity: "hard" | "warning";
}

export interface Classification {
  track: Track | null;
  profile: ProfileName | null;
  emphasis: Emphasis | null;
  language: Language | null;
  fit: FitLevel | null;
  gaps: AnalysisGap[];
  decided: string[];
}

const isRecord = (value: unknown): value is Record<string, unknown> =>
  typeof value === "object" && value !== null;

const gapsFrom = (value: unknown): AnalysisGap[] => {
  if (!Array.isArray(value)) {
    return [];
  }
  return value.flatMap((gap) => {
    if (!isRecord(gap) || typeof gap.requirement !== "string") {
      return [];
    }
    return gap.severity === "hard" || gap.severity === "warning"
      ? [{ requirement: gap.requirement, severity: gap.severity }]
      : [];
  });
};

/* A narrow read of the analysis document, which is carried as an opaque object on the
   wire on purpose: it is a versioned domain document, and a hand-written HTTP copy of
   its schema could only drift. Seven scalars and the gap list are read here so the user
   can see what they are deciding about; anything unreadable is reported as absent.

   It answers `null` unless the latest analysis *is* the active one. `latest_analysis` is
   the newest analysis of any snapshot, while `active_analysis_id` is the newest for the
   active snapshot; after a new JobSnapshot those diverge, and showing a superseded
   analysis's classification as the one under decision would be a real defect. */
export const classificationFromAnalysis = (detail: ApplicationDetail): Classification | null => {
  const record = detail.latest_analysis;
  if (record == null || detail.active_analysis_id == null) {
    return null;
  }
  if (record.id !== detail.active_analysis_id) {
    return null;
  }

  const analysis = record.analysis;
  const override = isRecord(analysis.user_override) ? analysis.user_override : {};

  return {
    track: isTrack(analysis.track) ? analysis.track : null,
    profile: isProfileName(analysis.profile) ? analysis.profile : null,
    emphasis: isEmphasis(analysis.emphasis) ? analysis.emphasis : null,
    language: isLanguage(analysis.language) ? analysis.language : null,
    fit: isFitLevel(analysis.fit) ? analysis.fit : null,
    gaps: gapsFrom(analysis.gaps),
    decided: Object.keys(override),
  };
};
