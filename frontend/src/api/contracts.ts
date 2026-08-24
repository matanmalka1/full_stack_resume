import type { components, operations, paths } from "../../../openapi/types";

export type ApiPaths = paths;
export type ApiOperations = operations;
export type ApiSchemas = components["schemas"];

export type ApplicationDetail = ApiSchemas["ApplicationDetailResponse"];
export type Operation = ApiSchemas["OperationResponse"];
export type OperationStatus = ApiSchemas["OperationStatus"];
export type OperationPhase = ApiSchemas["OperationPhase"];
export type WorkingDraft = ApiSchemas["WorkingDraftResponse"];

export type ApplicationIntake = ApiSchemas["DuplicateCheckRequest"];
export type CreateApplicationRequest = ApiSchemas["CreateApplicationRequest"];
export type CreatedApplication = ApiSchemas["CreateApplicationResponse"];
export type DuplicateCheckResult = ApiSchemas["DuplicateCheckResponse"];
export type DuplicateMatch = ApiSchemas["DuplicateMatchResponse"];
export type DuplicateMatchReason = DuplicateMatch["matched_on"][number];

/* The §9 action policy projection. The two lifecycle states are real unions rather
   than `string`, so a label map keyed by them stays exhaustive; the action fields are
   `string` at the boundary and are treated as open here on purpose. */
export type PreparationState = ApiSchemas["PreparationState"];
export type WorkingDraftState = ApiSchemas["WorkingDraftState"];
export type Reason = ApiSchemas["ReasonResponse"];
export type Warning = ApiSchemas["WarningResponse"];
export type BlockedAction = ApiSchemas["BlockedActionResponse"];

export type CreateAnalysisRequest = ApiSchemas["CreateAnalysisRequest"];
export type GenerateWorkingDraftRequest = ApiSchemas["GenerateWorkingDraftRequest"];

/* §13 `apply_analysis_decisions`: one synchronous commit, not an Operation. The four
   classification overrides are real unions rather than `string`, so the Hebrew option
   maps keyed by them stay exhaustive and an added Track fails the build. */
export type ApplyAnalysisDecisionsRequest = ApiSchemas["ApplyAnalysisDecisionsRequest"];
export type AnalysisDecisions = ApiSchemas["AnalysisDecisionsResponse"];
export type JobAnalysisRecord = ApiSchemas["JobAnalysisResponse"];
export type Track = ApiSchemas["Track"];
export type ProfileName = ApiSchemas["ProfileName"];
export type Emphasis = ApiSchemas["Emphasis"];
export type Language = NonNullable<ApplyAnalysisDecisionsRequest["language_override"]>;
