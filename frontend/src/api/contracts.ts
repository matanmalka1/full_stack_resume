import type { components } from "../../../openapi/types";

export type ApiSchemas = components["schemas"];

export type ApplicationDetail = ApiSchemas["ApplicationDetailResponse"];
export type RecruitmentTimelineItem = ApiSchemas["RecruitmentTimelineItemResponse"];
export type RecruitmentStatus = NonNullable<RecruitmentTimelineItem["to_status"]>;
export type TransitionableRecruitmentStatus = ApiSchemas["TransitionStatusRequest"]["target_status"];
export type ApplicationMutation = ApiSchemas["ApplicationMutationResponse"];
export type TransitionStatusRequest = ApiSchemas["TransitionStatusRequest"];
export type CorrectStatusRequest = ApiSchemas["CorrectStatusRequest"];
export type ExternalSubmissionRequest = ApiSchemas["ExternalSubmissionRequest"];
export type SubmitApplicationRequest = ApiSchemas["SubmitApplicationRequest"];
export type Submission = ApiSchemas["SubmissionResponse"];
export type NextActionRequest = ApiSchemas["NextActionRequest"];
export type ApplicationListResponse = ApiSchemas["ApplicationListResponse"];
/* The list query the backend answers. Filtering and ordering are its decision, not
   this client's: `preparation_state` is a computed projection rather than a stored
   column, so a client that narrowed by it would be deriving state a second time. */
export type ActivityFilter = ApiSchemas["ActivityFilter"];
export type ApplicationSort = ApiSchemas["ApplicationSort"];
/* The board's named questions. Each is a predicate over the §9 projection that the
   application layer answers, so it arrives as one filter rather than as rows this
   client re-decides. */
export type ApplicationPreset = ApiSchemas["ApplicationPreset"];
export type ApplicationListItem = ApiSchemas["ApplicationListItemResponse"];
export type Operation = ApiSchemas["OperationResponse"];
export type OperationStatus = ApiSchemas["OperationStatus"];
export type OperationPhase = ApiSchemas["OperationPhase"];
export type OperationType = ApiSchemas["OperationType"];
export type OperationFailureCode = ApiSchemas["OperationFailureCode"];
export type WorkingDraft = ApiSchemas["WorkingDraftResponse"];
export type ValidationRun = ApiSchemas["ValidationRunResponse"];
export type ValidationRunDetail = ApiSchemas["ValidationRunDetailResponse"];
export type ValidationReport = ApiSchemas["ValidationReportResponse"];
export type Approval = ApiSchemas["ApprovalResponse"];
export type ApprovedRevision = ApiSchemas["ApprovedRevisionResponse"];
export type DecisionMarkdown = ApiSchemas["DecisionMarkdownResponse"];
export type Settings = ApiSchemas["SettingsResponse"];
export type UpdateSettingsRequest = ApiSchemas["UpdateSettingsRequest"];
export type ReconciliationReport = ApiSchemas["ReconciliationResponse"];

export type ApplicationIntake = ApiSchemas["DuplicateCheckRequest"];
export type CreateApplicationRequest = ApiSchemas["CreateApplicationRequest"];
export type CreatedApplication = ApiSchemas["CreateApplicationResponse"];
export type ClosedApplication = ApiSchemas["CloseApplicationResponse"];
export type DuplicateCheckResult = ApiSchemas["DuplicateCheckResponse"];
export type DuplicateMatch = ApiSchemas["DuplicateMatchResponse"];
export type DuplicateMatchReason = DuplicateMatch["matched_on"][number];

/* The §9 action policy projection. The two lifecycle states are real unions rather
   than `string`, so a label map keyed by them stays exhaustive; the action fields are
   `string` at the boundary and are treated as open here on purpose. */
export type PreparationState = ApiSchemas["PreparationState"];
export type WorkingDraftState = ApiSchemas["WorkingDraftState"];
export type Reason = ApiSchemas["ReasonResponse"];

export type CreateAnalysisRequest = ApiSchemas["CreateAnalysisRequest"];
export type GenerateWorkingDraftRequest = ApiSchemas["GenerateWorkingDraftRequest"];
export type WorkingDraftVersionRequest = ApiSchemas["WorkingDraftVersionRequest"];
/* §14 the two ways out of a stale draft. `keep_previous` on the replacement is the Keep
   decision - the immutable historical snapshot is materialized before the replacement is
   attempted - and archiving produces that same snapshot without a replacement. */
export type ReplaceWorkingDraftRequest = ApiSchemas["ReplaceWorkingDraftRequest"];
export type ArchivedWorkingDraft = ApiSchemas["ArchivedWorkingDraftResponse"];
export type ApproveDraftRequest = ApiSchemas["ApproveDraftRequest"];
export type RenderRevisionRequest = ApiSchemas["RenderRevisionRequest"];

/* §13 `apply_analysis_decisions`: one synchronous commit, not an Operation. The four
   classification overrides are real unions rather than `string`, so the Hebrew option
   maps keyed by them stay exhaustive and an added Track fails the build. */
export type ApplyAnalysisDecisionsRequest = ApiSchemas["ApplyAnalysisDecisionsRequest"];
export type AnalysisDecisions = ApiSchemas["AnalysisDecisionsResponse"];
export type Track = ApiSchemas["Track"];
export type ProfileName = ApiSchemas["ProfileName"];
export type Emphasis = ApiSchemas["Emphasis"];
export type Language = NonNullable<ApplyAnalysisDecisionsRequest["language_override"]>;

/* §14/§20 the WorkingDraft the editor holds. `outline` is the editable structure derived
   from `source` on each read; `source` stays the opaque versioned document, on the same
   reasoning `JobAnalysisResponse.analysis` does. `ClaimType` is a real union,
   so the Hebrew status labels keyed by it stay exhaustive. */
export type DraftClaim = ApiSchemas["DraftClaimResponse"];
export type ClaimType = DraftClaim["claim_type"];

export type WorkingDraftFacts = ApiSchemas["WorkingDraftFactsResponse"];
export type DraftFact = ApiSchemas["DraftFactResponse"];
export type SelectionOutcome = NonNullable<DraftFact["outcome"]>;
export type OmissionReason = NonNullable<DraftFact["reason"]>;

export type ClaimPatch = ApiSchemas["ClaimPatchRequest"];
export type WorkingDraftUpdate = ApiSchemas["WorkingDraftUpdateResponse"];

export type Fact = ApiSchemas["FactResponse"];
export type FactStatus = ApiSchemas["FactStatus"];
export type FactList = ApiSchemas["FactListResponse"];
export type FactDetail = ApiSchemas["FactDetailResponse"];
export type FactHistory = ApiSchemas["FactHistoryResponse"];
export type FactMutation = ApiSchemas["FactMutationResponse"];
export type FactAttachment = ApiSchemas["FactAttachmentResponse"];
export type CreateFactRequest = ApiSchemas["FactContentRequest"];
export type CaptureClaimFactRequest = ApiSchemas["CaptureClaimFactRequest"];
export type FactTransitionRequest = ApiSchemas["FactTransitionRequest"];
export type AttachFactRequest = ApiSchemas["AttachFactRequest"];
export type ConfirmAndUseFactRequest = ApiSchemas["ConfirmAndUseFactRequest"];
export type ConfirmAndUseFact = ApiSchemas["ConfirmAndUseFactResponse"];

export type ApplySelectionChangeRequest = ApiSchemas["ApplySelectionChangeRequest"];
export type SelectionChange = ApiSchemas["SelectionChangeResponse"];

export type RegenerateSectionRequest = ApiSchemas["RegenerateSectionRequest"];
export type RegenerateClaimRequest = ApiSchemas["RegenerateClaimRequest"];
