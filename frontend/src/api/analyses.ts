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

/* What this screen may submit: the four classification overrides. There is nothing to
   accept - low Fit and hard gaps are shown, not gated - so the form carries no acceptance
   fields. The fact overlay is deliberately absent too: it has its own SelectionPlan query
   and command, and the backend refuses a submission carrying a fact overlay together with
   a classification decision, so omitting the fields makes that refusal unreachable here by
   construction rather than by a client-side copy of a rule. */
export type ClassificationDecisions = Pick<
  ApplyAnalysisDecisionsRequest,
  "track_override" | "profile_override" | "emphasis_override" | "language_override"
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
  /* The fact overlay is omitted by type, not merely left unset: it belongs to a dedicated
     control, and this classification form must not manufacture an empty decision for a
     field it does not present. */
  const body: Omit<ApplyAnalysisDecisionsRequest, "pinned_fact_ids" | "excluded_fact_ids"> = {
    application_id: applicationId,
    expected_analysis_id: analysisId,
    ...(activeSelectionPlanId === null ? {} : { expected_selection_plan_id: activeSelectionPlanId }),
    ...(decisions.track_override == null ? {} : { track_override: decisions.track_override }),
    ...(decisions.profile_override == null ? {} : { profile_override: decisions.profile_override }),
    ...(decisions.emphasis_override == null ? {} : { emphasis_override: decisions.emphasis_override }),
    ...(decisions.language_override == null ? {} : { language_override: decisions.language_override }),
  };

  const response = await apiRequest<AnalysisDecisions>(applyDecisionsPath(analysisId), {
    method: "POST",
    body,
  });
  return response.data;
};

export type RequirementCoverage = "matched" | "partial" | "unsupported" | "unknown";
export type RequirementImportance = "mandatory" | "preferred" | "unknown";
export type ShortfallSeverity = "none" | "minor" | "material" | "unknown";

/* One thing the employer asked for, and what the canonical facts can truthfully show for
   it - the mirror of the backend's `Requirement`. `coverage` is whether it is met;
   `supportingFactIds` is whether evidence exists; the two are read independently so a
   demanded proficiency the candidate falls short of can still list the fact carrying the
   lower value. `boundaryFactIds` names canonical facts that explicitly cap coverage - never
   additional support, only the reason coverage stops short of `matched`. */
export interface Requirement {
  requirementId: string;
  text: string;
  importance: RequirementImportance;
  coverage: RequirementCoverage;
  /* Missing only on immutable analyses created before this field existed. */
  shortfallSeverity?: ShortfallSeverity | null;
  shortfallReason?: string | null;
  supportingFactIds: string[];
  boundaryFactIds: string[];
}

/* A requirement the facts do not fully answer, as the backend projected it at read time.
   Shown to the user and gating nothing: a hard gap marks a demanded requirement the facts
   do not support, and the user may still draft, approve and submit. */
interface AnalysisGap {
  requirementId: string;
  requirement: string;
  severity: "hard" | "warning";
  reason: string;
  substituteFactIds: string[];
}

/* Where the reading was narrowed: a citation dropped, a coverage lowered, a quote the
   posting does not carry. Information for the user - it explains why the analysis claims
   less than the posting seems to ask for - and never a blocker. */
export interface AnalysisIssue {
  code: string;
  requirementIndex: number | null;
}

export interface Classification {
  track: Track | null;
  profile: ProfileName | null;
  emphasis: Emphasis | null;
  language: Language | null;
  /* Projected by the backend from the requirements when the response is built. */
  fit: FitLevel | null;
  fitScore: number | null;
  gaps: AnalysisGap[];
  decided: string[];
  /* The provider's short account of its reading. */
  summary: string | null;
  keywords: string[];
  /* The complete requirement picture, matched requirements included; `gaps` is its unmet
     projection. */
  requirements: Requirement[];
  unreadableRequirementCount: number;
  issues: AnalysisIssue[];
  /* The share of requirements whose text the engine found in the posting. */
  sourceCoverage: number | null;
}

const isRecord = (value: unknown): value is Record<string, unknown> => typeof value === "object" && value !== null;

/* A 0..1 float in the domain model. A non-finite value is absent rather than rendered, so a
   malformed document cannot print "NaN%". */
const finiteFraction = (value: unknown): number | null =>
  typeof value === "number" && Number.isFinite(value) ? value : null;

const stringsFrom = (value: unknown): string[] =>
  Array.isArray(value) ? value.filter((item): item is string => typeof item === "string") : [];

const isRequirementCoverage = (value: unknown): value is RequirementCoverage =>
  value === "matched" || value === "partial" || value === "unsupported" || value === "unknown";

const isRequirementImportance = (value: unknown): value is RequirementImportance =>
  value === "mandatory" || value === "preferred" || value === "unknown";

const isShortfallSeverity = (value: unknown): value is ShortfallSeverity =>
  value === "none" || value === "minor" || value === "material" || value === "unknown";

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
      !isRequirementImportance(requirement.importance) ||
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
        importance: requirement.importance,
        coverage: requirement.coverage,
        shortfallSeverity: isShortfallSeverity(requirement.shortfall_severity)
          ? requirement.shortfall_severity
          : null,
        shortfallReason:
          typeof requirement.shortfall_reason === "string" ? requirement.shortfall_reason : null,
        supportingFactIds: stringsFrom(requirement.supporting_fact_ids),
        boundaryFactIds: stringsFrom(requirement.boundary_fact_ids),
      },
    ];
  });
  return { items, unreadableCount };
};

const issuesFrom = (value: unknown): AnalysisIssue[] =>
  Array.isArray(value)
    ? value.flatMap((issue) =>
        isRecord(issue) && typeof issue.code === "string"
          ? [
              {
                code: issue.code,
                requirementIndex: typeof issue.requirement_index === "number" ? issue.requirement_index : null,
              },
            ]
          : [],
      )
    : [];

/* A narrow read of the analysis document, which is carried as an opaque object on the wire
   on purpose: it is a versioned domain document, and a hand-written HTTP copy of its schema
   could only drift. Fit and gaps are not in it - they are typed projections beside it on the
   response. Unreadable requirements are counted so a partially malformed list cannot look
   complete; other unreadable fields stay absent.

   It answers `null` unless the latest analysis *is* the active one. `latest_analysis` is the
   newest analysis of any snapshot, while `active_analysis_id` is the newest for the active
   snapshot; after a new JobSnapshot those diverge, and showing a superseded analysis's
   classification as the one under decision would be a real defect. */
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
    /* Emphasis is effective at SelectionPlan level. The Application scalar is advanced
       with that active plan, while the immutable analysis keeps the classification value it
       originally carried. */
    emphasis: isEmphasis(detail.application.emphasis)
      ? detail.application.emphasis
      : isEmphasis(analysis.emphasis)
        ? analysis.emphasis
        : null,
    language: isLanguage(analysis.language) ? analysis.language : null,
    fit: isFitLevel(record.fit_level) ? record.fit_level : null,
    fitScore: finiteFraction(record.fit_score),
    gaps: (record.gaps ?? []).map((gap) => ({
      requirementId: gap.requirement_id,
      requirement: gap.requirement,
      severity: gap.severity,
      reason: gap.reason,
      substituteFactIds: gap.substitute_fact_ids ?? [],
    })),
    decided: Object.keys(override),
    summary: typeof analysis.summary === "string" ? analysis.summary : null,
    keywords: stringsFrom(analysis.keywords),
    requirements: parsedRequirements.items,
    unreadableRequirementCount: parsedRequirements.unreadableCount,
    issues: issuesFrom(analysis.issues),
    sourceCoverage: finiteFraction(analysis.source_coverage),
  };
};
