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
export type OperationOutput = ApiSchemas["OperationOutputResponse"];
export type OperationStatus = ApiSchemas["OperationStatus"];
export type OperationPhase = ApiSchemas["OperationPhase"];
export type OperationType = ApiSchemas["OperationType"];
export type OperationFailureCode = ApiSchemas["OperationFailureCode"];
export type ValidationReport = ApiSchemas["ValidationReportResponse"];
export type Settings = ApiSchemas["SettingsResponse"];
export type UpdateSettingsRequest = ApiSchemas["UpdateSettingsRequest"];
export type ReconciliationReport = ApiSchemas["ReconciliationResponse"];

export type ApplicationIntake = ApiSchemas["DuplicateCheckRequest"];
export type CreateApplicationRequest = ApiSchemas["CreateApplicationRequest"];
export type CreatedApplication = ApiSchemas["CreateApplicationResponse"];
export type ClosedApplication = ApiSchemas["CloseApplicationResponse"];
export type DeletedApplication = ApiSchemas["DeleteApplicationResponse"];
/* A new posting version for an Application that already exists. It creates a snapshot
   beside the ones on record rather than editing one, so the response names the new
   snapshot and nothing else. */
export type CreateJobSnapshotRequest = ApiSchemas["CreateJobSnapshotRequest"];
export type CreatedJobSnapshot = ApiSchemas["CreateJobSnapshotResponse"];
export type UpdateApplicationNotesRequest = ApiSchemas["UpdateApplicationNotesRequest"];
export type UpdatedApplicationNotes = ApiSchemas["UpdateApplicationNotesResponse"];
export type DuplicateCheckResult = ApiSchemas["DuplicateCheckResponse"];
export type DuplicateMatch = ApiSchemas["DuplicateMatchResponse"];
export type DuplicateMatchReason = DuplicateMatch["matched_on"][number];

/* The §9 action policy projection. The lifecycle states are real unions rather
   than `string`, so a label map keyed by them stays exhaustive; the action fields are
   `string` at the boundary and are treated as open here on purpose. */
export type PreparationState = ApiSchemas["PreparationState"];
export type ContentCheck = ApiSchemas["ContentCheck"];
export type Reason = ApiSchemas["ReasonResponse"];

/* §3/§14-§16 the one CV document per Application. `document_hash` is its token: the
   read returns it as the ETag, the autosave PATCH sends it as If-Match, and every action
   carries it as `expected_document_hash`. `content` stays the opaque versioned document;
   `outline` is the editable structure derived from it on each read. */
export type CVDocument = ApiSchemas["DocumentResponse"];
export type DocumentCandidate = ApiSchemas["DocumentCandidateResponse"];
export type DocumentMutation = ApiSchemas["DocumentMutationResponse"];
export type DocumentCheck = ApiSchemas["DocumentCheckResponse"];
export type DocumentActionRequest = ApiSchemas["DocumentActionRequest"];
export type UpdateDocumentRequest = ApiSchemas["UpdateDocumentRequest"];
export type UpdateSelectionRequest = ApiSchemas["UpdateSelectionRequest"];
export type ProposeSelectionRequest = ApiSchemas["ProposeSelectionRequest"];
export type BuildFromAnalysisRequest = ApiSchemas["BuildFromAnalysisRequest"];
export type CreateDraftRequest = ApiSchemas["CreateDraftRequest"];
export type RegenerateDocumentSectionRequest = ApiSchemas["RegenerateDocumentSectionRequest"];
export type RegenerateDocumentClaimRequest = ApiSchemas["RegenerateDocumentClaimRequest"];
export type DecisionExport = ApiSchemas["DecisionExportResponse"];

export type CreateAnalysisRequest = ApiSchemas["CreateAnalysisRequest"];

/* §13 `apply_analysis_decisions`: one synchronous matching-configuration commit, not an
   Operation. The classification overrides are real unions rather than `string`, so the
   Hebrew option maps keyed by them stay exhaustive and an added Track fails the build. */
export type ApplyAnalysisDecisionsRequest = ApiSchemas["ApplyAnalysisDecisionsRequest"];
export type AnalysisDecisions = ApiSchemas["AnalysisDecisionsResponse"];
/* The analysis record's own provenance - provider, model, version, timestamp - as
   opposed to `Classification`, which reads the opaque `analysis` document it carries. */
export type JobAnalysisRecord = ApiSchemas["JobAnalysisResponse"];
export type Track = ApiSchemas["Track"];
export type ProfileName = ApiSchemas["ProfileName"];
export type Emphasis = ApiSchemas["Emphasis"];
export type Language = NonNullable<ApplyAnalysisDecisionsRequest["language_override"]>;

/* §14/§20 the document content the editor holds. `outline` is the editable structure
   derived from `content` on each read; `content` stays the opaque versioned document, on
   the same reasoning `JobAnalysisResponse.analysis` does. `ClaimType` is a real union,
   so the Hebrew status labels keyed by it stay exhaustive. */
export type DraftClaim = ApiSchemas["DraftClaimResponse"];
export type ClaimType = DraftClaim["claim_type"];

export type DraftFact = ApiSchemas["DraftFactResponse"];
export type SelectionOutcome = NonNullable<DraftFact["outcome"]>;
export type OmissionReason = NonNullable<DraftFact["reason"]>;

export type ClaimPatch = ApiSchemas["ClaimPatchRequest"];
export type ClaimAddition = ApiSchemas["ClaimAdditionRequest"];

export type Fact = ApiSchemas["FactResponse"];
export type FactStatus = ApiSchemas["FactStatus"];
export type FactList = ApiSchemas["FactListResponse"];
export type FactDetail = ApiSchemas["FactDetailResponse"];
export type FactHistory = ApiSchemas["FactHistoryResponse"];
export type FactMutation = ApiSchemas["FactMutationResponse"];
export type FactAttachment = ApiSchemas["FactAttachmentResponse"];
export type FactAttachmentTargets = ApiSchemas["FactAttachmentTargetsResponse"];
export type CreateFactRequest = ApiSchemas["FactContentRequest"];
export type CaptureClaimFactRequest = ApiSchemas["CaptureClaimFactRequest"];
export type FactTransitionRequest = ApiSchemas["FactTransitionRequest"];
export type AttachFactRequest = ApiSchemas["AttachFactRequest"];
export type ConfirmAndUseFactRequest = ApiSchemas["ConfirmAndUseFactRequest"];
export type ConfirmAndUseFact = ApiSchemas["ConfirmAndUseFactResponse"];

export type JobSnapshotHistory = ApiSchemas["JobSnapshotHistoryResponse"];
