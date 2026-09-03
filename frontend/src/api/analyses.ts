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
} from "../pages/application/analysisLabels";

/* What this screen may submit: the four classification decisions, the two acceptances
   recorded on the analysis, and the per-gap acceptance recorded on the SelectionPlan.
   The fact overlay is deliberately absent: no endpoint exposes the candidate fact pool
   to the browser, and the backend refuses a submission carrying a fact overlay together
   with a classification decision. Omitting the fields makes that refusal unreachable
   from here by construction rather than by a client-side copy of a server rule.

   A gap acceptance carries no such restriction and rides along with a classification
   decision in the same commit: it names a requirement rather than a fact, and the server
   re-checks it against the analysis it is about to write. */
export type ClassificationDecisions = Pick<
  ApplyAnalysisDecisionsRequest,
  | "track_override"
  | "profile_override"
  | "emphasis_override"
  | "language_override"
  | "accept_low_fit"
  | "accept_incomplete_analysis"
  | "accepted_requirement_ids"
  | "acceptance_reason"
>;

const applyDecisionsPath = (analysisId: string): ApiPath =>
  `/api/v1/analyses/${encodeURIComponent(analysisId)}/apply-decisions`;

/* The gap acceptance, with the plan id it is only ever valid against. The two travel
   together because the server refuses them apart: an acceptance without
   `expected_selection_plan_id` is a decision applied to whatever plan is active now
   rather than to the one the reader was shown, and that rebase is exactly what the check
   exists to prevent.

   An empty acceptance therefore carries no plan id, so an unrelated decision - a Track
   override on a screen that also shows gaps - is not turned into an optimistic write
   against a plan it says nothing about.

   Marking a gap with no active SelectionPlan is refused here rather than sent and refused
   there. It cannot be reached from the screen, which withholds the controls in that state;
   raising is what keeps a decision from being dropped silently if it ever is. */
const acceptanceFields = (
  decisions: ClassificationDecisions,
  activeSelectionPlanId: string | null,
): Pick<ApplyAnalysisDecisionsRequest, "accepted_requirement_ids"> &
  Partial<Pick<ApplyAnalysisDecisionsRequest, "acceptance_reason" | "expected_selection_plan_id">> => {
  const accepted = decisions.accepted_requirement_ids;
  if (accepted.length === 0) {
    return { accepted_requirement_ids: [] };
  }
  if (activeSelectionPlanId === null) {
    throw new Error("a gap acceptance was submitted without an active SelectionPlan to record it against");
  }
  /* Blank is absent, as everywhere else on this form: the reason is optional, and `""`
     would be a recorded reason that says nothing. */
  const reason = decisions.acceptance_reason?.trim() ?? "";

  return {
    accepted_requirement_ids: accepted,
    expected_selection_plan_id: activeSelectionPlanId,
    ...(reason === "" ? {} : { acceptance_reason: reason }),
  };
};

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
  activeSelectionPlanId: string | null,
): Promise<AnalysisDecisions> => {
  /* The fact overlay is omitted by type, not merely left unset: naming it in the `Omit`
     is what makes adding a field here a compile error rather than a quiet change of what
     this screen commits. */
  const body: Omit<ApplyAnalysisDecisionsRequest, "pinned_fact_ids" | "excluded_fact_ids"> = {
    application_id: applicationId,
    accept_low_fit: decisions.accept_low_fit,
    accept_incomplete_analysis: decisions.accept_incomplete_analysis,
    ...(decisions.track_override == null ? {} : { track_override: decisions.track_override }),
    ...(decisions.profile_override == null ? {} : { profile_override: decisions.profile_override }),
    ...(decisions.emphasis_override == null ? {} : { emphasis_override: decisions.emphasis_override }),
    ...(decisions.language_override == null ? {} : { language_override: decisions.language_override }),
    ...acceptanceFields(decisions, activeSelectionPlanId),
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

interface AnalysisGap {
  requirement: string;
  severity: "hard" | "warning";
  reason: string;
  /* The Requirement this gap projects, and the only thing an acceptance may name. Absent
     on an analysis written before requirement extraction existed, whose stored gaps stay
     authoritative exactly as recorded - and which therefore has no acceptable gap at all,
     since the server refuses any id that names no hard gap of the analysis being written. */
  requirementId: string | null;
}

export interface Classification {
  track: Track | null;
  profile: ProfileName | null;
  emphasis: Emphasis | null;
  language: Language | null;
  fit: FitLevel | null;
  gaps: AnalysisGap[];
  decided: string[];
  /* The descriptive half of the document: what the analysis concluded and why, as
     opposed to the four scalars a decision may override. Read the same defensively
     narrow way - an unreadable field is absent rather than `undefined` on screen. */
  rationale: string | null;
  confidence: number | null;
  /* Set together, only when an AI proposal was actually merged in: `confidence` above is
     `min(deterministicConfidence, proposalConfidence)` in that case, so the two together
     are what explain a merged number a reader could otherwise not account for. Both stay
     null on the deterministic-only path, where `confidence` is already the whole story. */
  deterministicConfidence: number | null;
  proposalConfidence: number | null;
  keywords: string[];
  mandatoryRequirements: string[];
  preferredRequirements: string[];
  /* Why the classification still needs a decision, as the analysis recorded it. The
     backend clears a reason only when an override that actually answers it is applied,
     so this list is what remains open rather than everything ever raised. */
  approvalReasons: string[];
}

const isRecord = (value: unknown): value is Record<string, unknown> => typeof value === "object" && value !== null;

/* A 0..1 float in the domain model. A non-finite value is absent rather than rendered,
   so a malformed document cannot print "NaN%". */
const finiteConfidence = (value: unknown): number | null =>
  typeof value === "number" && Number.isFinite(value) ? value : null;

const stringsFrom = (value: unknown): string[] =>
  Array.isArray(value) ? value.filter((item): item is string => typeof item === "string") : [];

const gapsFrom = (value: unknown): AnalysisGap[] => {
  if (!Array.isArray(value)) {
    return [];
  }
  return value.flatMap((gap) => {
    if (!isRecord(gap) || typeof gap.requirement !== "string") {
      return [];
    }
    return gap.severity === "hard" || gap.severity === "warning"
      ? [
          {
            requirement: gap.requirement,
            severity: gap.severity,
            reason: typeof gap.reason === "string" ? gap.reason : "",
            requirementId: typeof gap.requirement_id === "string" ? gap.requirement_id : null,
          },
        ]
      : [];
  });
};

/* A narrow read of the analysis document, which is carried as an opaque object on the
   wire on purpose: it is a versioned domain document, and a hand-written HTTP copy of
   its schema could only drift. The scalars, the gap list, and the descriptive fields the
   analysis screen shows are read here so the user can see both what they are deciding
   about and what the analysis concluded; anything unreadable is reported as absent.

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
    rationale: typeof analysis.rationale === "string" ? analysis.rationale : null,
    confidence: finiteConfidence(analysis.confidence),
    deterministicConfidence: finiteConfidence(analysis.deterministic_confidence),
    proposalConfidence: finiteConfidence(analysis.proposal_confidence),
    keywords: stringsFrom(analysis.keywords),
    mandatoryRequirements: stringsFrom(analysis.mandatory_requirements),
    preferredRequirements: stringsFrom(analysis.preferred_requirements),
    /* The full recorded list, read as it arrives. Which of these are still unresolved is
       the domain's rule - a reason clears when an override that answers it is applied -
       and that rule is deliberately not copied here: the projection already publishes the
       verdict as a review reason, so a second client-side copy could only drift from it.
       This list explains that verdict rather than recomputing it. */
    approvalReasons: stringsFrom(analysis.approval_reasons),
  };
};
