import { queryOptions } from "@tanstack/react-query";

import { type ApiPath, type ApiResponse, apiRequest } from "./client";
import type {
  AnalysisDecisions,
  ApplicationDetail,
  ApplyAnalysisDecisionsRequest,
  CreatedSelectionPlan,
  CreateSelectionPlanRequest,
  Emphasis,
  Language,
  ProfileName,
  Operation,
  SelectionPlanDetail,
  Track,
} from "./contracts";
import { type QueuedOperation, queuedOperation } from "./operations";
import { type FitLevel, isEmphasis, isFitLevel, isLanguage, isProfileName, isTrack } from "./classificationValues";

/* What this screen may submit: matching decisions and the two acceptances
   recorded on the analysis, and the per-gap acceptance recorded on the SelectionPlan.
   The fact overlay is deliberately absent from this classification form. It has its own
   SelectionPlan query and command: the backend refuses a submission carrying a fact
   overlay together with a classification decision, so omitting the fields makes that
   refusal unreachable here by construction rather than by a client-side copy of a rule.

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

const selectionPlansPath = (analysisId: string): ApiPath =>
  `/api/v1/analyses/${encodeURIComponent(analysisId)}/selection-plans`;

const selectionPlanPath = (selectionPlanId: string): ApiPath =>
  `/api/v1/selection-plans/${encodeURIComponent(selectionPlanId)}`;

const selectionPlanQueryKey = (selectionPlanId: string) => ["selection-plan", selectionPlanId] as const;

export const selectionPlanQueryOptions = (selectionPlanId: string) =>
  queryOptions({
    queryKey: selectionPlanQueryKey(selectionPlanId),
    queryFn: async ({ signal }): Promise<SelectionPlanDetail> => {
      const response = await apiRequest<SelectionPlanDetail>(selectionPlanPath(selectionPlanId), { signal });
      return response.data;
    },
  });

export type SelectionPlanCreation =
  { kind: "created"; result: CreatedSelectionPlan } | { kind: "queued"; operation: Operation };

export const createSelectionPlan = async (
  analysisId: string,
  request: CreateSelectionPlanRequest,
  idempotencyKey?: string,
): Promise<SelectionPlanCreation> => {
  const response = await apiRequest<CreatedSelectionPlan | Operation>(selectionPlansPath(analysisId), {
    method: "POST",
    body: request,
    ...(idempotencyKey === undefined ? {} : { idempotencyKey }),
  });
  if (response.status === 201 && request.mode === "deterministic") {
    return { kind: "created", result: response.data as CreatedSelectionPlan };
  }
  if (response.status === 202 && request.mode === "ai") {
    const queued: QueuedOperation = queuedOperation(response as ApiResponse<Operation>);
    return { kind: "queued", operation: queued.operation };
  }
  throw new Error("SelectionPlan creation returned an unexpected status");
};

/* The gap-specific fields. The active plan id is now a CAS source for every decision and
   is added by `applyAnalysisDecisions` below; this helper only validates that a gap
   acceptance cannot exist when the projection showed no plan at all.

   Marking a gap with no active SelectionPlan is refused here rather than sent and refused
   there. It cannot be reached from the screen, which withholds the controls in that state;
   raising is what keeps a decision from being dropped silently if it ever is. */
const acceptanceFields = (
  decisions: ClassificationDecisions,
  activeSelectionPlanId: string | null,
): Pick<ApplyAnalysisDecisionsRequest, "accepted_requirement_ids"> &
  Partial<Pick<ApplyAnalysisDecisionsRequest, "acceptance_reason">> => {
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
    ...(reason === "" ? {} : { acceptance_reason: reason }),
  };
};

/* §13: synchronous, one commit, no Operation - so no `Idempotency-Key` and no
   `202`/`Location` obligation. `application_id`, `expected_analysis_id`, and the active
   plan are stated rather than inferred: the first names ownership and the latter two
   are the exact context the form read.

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
  /* The fact overlay and requirement-interpretation corrections are omitted by type, not
     merely left unset. Each belongs to a dedicated control; this classification form must
     not manufacture an empty decision for a field it does not present. Naming them in the
     `Omit` keeps the payload honest while the request schema's server-side defaults retain
     the existing values. */
  const body: Omit<
    ApplyAnalysisDecisionsRequest,
    "pinned_fact_ids" | "excluded_fact_ids" | "requirement_interpretations"
  > = {
    application_id: applicationId,
    expected_analysis_id: analysisId,
    ...(activeSelectionPlanId === null ? {} : { expected_selection_plan_id: activeSelectionPlanId }),
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

export type RequirementCoverage = "matched" | "partial" | "unsupported" | "undetermined";

interface MissingComponent {
  componentId: string;
  label: string;
  demanded: string | null;
}

/* One thing the employer asked for, and what the canonical facts can truthfully show
   for it - the mirror of the backend's `Requirement`. `coverage` is whether it is met;
   `supportingFactIds` is whether evidence exists; the two are read independently so a
   demanded proficiency the candidate falls short of can still list the fact carrying
   the lower value. `boundaryFactIds` names facts that explicitly cap coverage - they
   are never additional support, only the reason coverage stops short of `matched`. */
export interface Requirement {
  requirementId: string;
  text: string;
  mandatory: boolean;
  coverage: RequirementCoverage;
  supportingFactIds: string[];
  boundaryFactIds: string[];
  missingComponents: MissingComponent[];
}

interface AnalysisGap {
  requirement: string;
  severity: "hard" | "warning";
  reason: string;
  /* The Requirement this gap projects, and the only thing an acceptance may name. */
  requirementId: string;
}

export interface Classification {
  track: Track | null;
  profile: ProfileName | null;
  emphasis: Emphasis | null;
  language: Language | null;
  fit: FitLevel | null;
  /* The canonical numeric measure `fit` is read off: a weighted fraction of
     requirement coverage, distinct from `confidence` below (how sure the
     classifier is about its own read of the posting, not how well the
     candidate matches it). Null only when nothing was assessed at all - same
     condition that makes `fit` itself `unknown`. */
  fitScore: number | null;
  gaps: AnalysisGap[];
  decided: string[];
  /* The descriptive half of the document: what the analysis concluded and why, as
     opposed to the four scalars a decision may override. Read the same defensively
     narrow way - an unreadable field is absent rather than `undefined` on screen. */
  rationale: string | null;
  confidence: number | null;
  keywords: string[];
  mandatoryRequirements: string[];
  preferredRequirements: string[];
  /* The complete requirement picture, matched requirements included; `gaps` is
     its unmet projection. */
  requirements: Requirement[];
  unreadableRequirementCount: number;
  /* Why the analysis still needs a decision, as the analysis recorded it. The
     backend clears a reason only when an override that actually answers it is applied,
     so this list is what remains open rather than everything ever raised. */
  approvalReasons: string[];
}

const isRecord = (value: unknown): value is Record<string, unknown> => typeof value === "object" && value !== null;

/* A 0..1 float in the domain model. A non-finite value is absent rather than rendered,
   so a malformed document cannot print "NaN%". */
const finiteFraction = (value: unknown): number | null =>
  typeof value === "number" && Number.isFinite(value) ? value : null;

const stringsFrom = (value: unknown): string[] =>
  Array.isArray(value) ? value.filter((item): item is string => typeof item === "string") : [];

const gapsFrom = (value: unknown): AnalysisGap[] => {
  if (!Array.isArray(value)) {
    return [];
  }
  return value.flatMap((gap) => {
    if (!isRecord(gap) || typeof gap.requirement !== "string" || typeof gap.requirement_id !== "string") {
      return [];
    }
    return gap.severity === "hard" || gap.severity === "warning"
      ? [
          {
            requirement: gap.requirement,
            severity: gap.severity,
            reason: typeof gap.reason === "string" ? gap.reason : "",
            requirementId: gap.requirement_id,
          },
        ]
      : [];
  });
};

const isRequirementCoverage = (value: unknown): value is RequirementCoverage =>
  value === "matched" || value === "partial" || value === "unsupported" || value === "undetermined";

const missingComponentsFrom = (value: unknown): MissingComponent[] => {
  if (!Array.isArray(value)) {
    return [];
  }
  return value.flatMap((component) => {
    if (!isRecord(component) || typeof component.component_id !== "string" || typeof component.label !== "string") {
      return [];
    }
    return [
      {
        componentId: component.component_id,
        label: component.label,
        demanded: typeof component.demanded === "string" ? component.demanded : null,
      },
    ];
  });
};

const requirementsFrom = (value: unknown): { items: Requirement[]; unreadableCount: number } => {
  if (!Array.isArray(value)) {
    return { items: [], unreadableCount: 0 };
  }
  const seenIds = new Set<string>();
  let unreadableCount = 0;
  const items = value.flatMap((requirement) => {
    if (
      !isRecord(requirement) ||
      typeof requirement.requirement_id !== "string" ||
      requirement.requirement_id.trim() === "" ||
      seenIds.has(requirement.requirement_id) ||
      typeof requirement.text !== "string" ||
      requirement.text.trim() === "" ||
      typeof requirement.mandatory !== "boolean" ||
      !isRequirementCoverage(requirement.coverage)
    ) {
      unreadableCount += 1;
      return [];
    }
    seenIds.add(requirement.requirement_id);
    return [
      {
        requirementId: requirement.requirement_id,
        text: requirement.text,
        mandatory: requirement.mandatory,
        coverage: requirement.coverage,
        supportingFactIds: stringsFrom(requirement.supporting_fact_ids),
        boundaryFactIds: stringsFrom(requirement.boundary_fact_ids),
        missingComponents: missingComponentsFrom(requirement.missing_components),
      },
    ];
  });
  return { items, unreadableCount };
};

/* A narrow read of the analysis document, which is carried as an opaque object on the
   wire on purpose: it is a versioned domain document, and a hand-written HTTP copy of
   its schema could only drift. The scalars, the gap list, and the descriptive fields the
   analysis screen shows are read here so the user can see both what they are deciding
   about and what the analysis concluded. Unreadable requirements are counted so a
   partially malformed list cannot look complete; other unreadable fields stay absent.

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
  const parsedRequirements = requirementsFrom(analysis.requirements);

  return {
    track: isTrack(analysis.track) ? analysis.track : null,
    profile: isProfileName(analysis.profile) ? analysis.profile : null,
    /* Emphasis is effective at SelectionPlan level. The Application scalar is
       advanced with that active plan, while the immutable analysis keeps the
       classification value it originally carried. */
    emphasis: isEmphasis(detail.application.emphasis)
      ? detail.application.emphasis
      : isEmphasis(analysis.emphasis)
        ? analysis.emphasis
        : null,
    language: isLanguage(analysis.language) ? analysis.language : null,
    fit: isFitLevel(analysis.fit) ? analysis.fit : null,
    fitScore: finiteFraction(analysis.fit_score),
    gaps: gapsFrom(analysis.gaps),
    decided: Object.keys(override),
    rationale: typeof analysis.rationale === "string" ? analysis.rationale : null,
    confidence: finiteFraction(analysis.confidence),
    keywords: stringsFrom(analysis.keywords),
    mandatoryRequirements: stringsFrom(analysis.mandatory_requirements),
    preferredRequirements: stringsFrom(analysis.preferred_requirements),
    requirements: parsedRequirements.items,
    unreadableRequirementCount: parsedRequirements.unreadableCount,
    /* The full recorded list, read as it arrives. Which of these are still unresolved is
       the domain's rule - a reason clears when an override that answers it is applied -
       and that rule is deliberately not copied here: the projection already publishes the
       verdict as a review reason, so a second client-side copy could only drift from it.
       This list explains that verdict rather than recomputing it. */
    approvalReasons: stringsFrom(analysis.approval_reasons),
  };
};

/* Acceptances are durable facts on the analysis, while `review_reasons` says whether
   they are still being requested. Read the exact stored value so an absent reason alone
   is never presented as proof that the user approved low fit. */
export const lowFitAcceptedFromAnalysis = (detail: ApplicationDetail): boolean => {
  const record = detail.latest_analysis;
  if (record == null || record.id !== detail.active_analysis_id) {
    return false;
  }
  const override = isRecord(record.analysis.user_override) ? record.analysis.user_override : {};
  return override.fit === "accepted-low-fit";
};
