import { queryOptions } from "@tanstack/react-query";

import { ApiProblem, type ApiPath, apiRequest } from "./client";
import type {
  ActivityFilter,
  ApplicationDetail,
  ApplicationIntake,
  ApplicationListResponse,
  ApplicationPreset,
  ApplicationSort,
  CreateAnalysisRequest,
  CreateApplicationRequest,
  ClosedApplication,
  CreatedApplication,
  DuplicateCheckResult,
  DuplicateMatch,
  DuplicateMatchReason,
  GenerateWorkingDraftRequest,
  Operation,
  PreparationState,
  RecruitmentStatus,
} from "./contracts";
import {
  OPERATION_POLL_INTERVAL_MS,
  isTerminalOperation,
  type QueuedOperation,
  queuedOperation,
} from "./operations";

/* The only intake limit this module keeps. It is not a second copy of the intake
   policy - the server revalidates size, control characters, and URL syntax and stays
   authoritative - but reading a multi-hundred-megabyte file into the tab before the
   server can refuse it freezes the browser, so the size is checked before the read. */
export const JOB_TEXT_MAX_BYTES = 1024 * 1024;

export const DUPLICATE_ACKNOWLEDGEMENT_REQUIRED = "DUPLICATE_ACKNOWLEDGEMENT_REQUIRED";

export const duplicateCheck = async (intake: ApplicationIntake): Promise<DuplicateMatch[]> => {
  const response = await apiRequest<DuplicateCheckResult>("/api/v1/applications/duplicate-check", {
    method: "POST",
    body: intake,
  });
  return response.data.matches;
};

export const createApplication = async (
  intake: ApplicationIntake,
  acknowledgedDuplicates: boolean,
): Promise<CreatedApplication> => {
  const body: CreateApplicationRequest = {
    ...intake,
    acknowledged_duplicates: acknowledgedDuplicates,
  };
  const response = await apiRequest<CreatedApplication>("/api/v1/applications", {
    method: "POST",
    body,
  });
  return response.data;
};

/* Exhaustive over the generated union, so a detection reason added to the backend fails
   the build here rather than arriving as a key nothing can translate. The runtime set is
   derived from it rather than written a second time. */
const duplicateMatchReasons: Record<DuplicateMatchReason, true> = {
  source_url: true,
  normalized_text: true,
  company_title: true,
};

const isDuplicateMatchReason = (value: unknown): value is DuplicateMatchReason =>
  typeof value === "string" && Object.hasOwn(duplicateMatchReasons, value);

const isDuplicateMatch = (value: unknown): value is DuplicateMatch => {
  if (typeof value !== "object" || value === null) {
    return false;
  }

  const candidate = value as Record<string, unknown>;

  return (
    typeof candidate.application_id === "string" &&
    typeof candidate.company === "string" &&
    typeof candidate.target_role === "string" &&
    Array.isArray(candidate.matched_on) &&
    candidate.matched_on.every(isDuplicateMatchReason)
  );
};

/* Duplicate detection runs twice by design: once before creation for the user, and
   again inside the create command. The second one is the authority, so its refusal is
   read back as the same duplicate choice rather than as a failed request. An empty
   list means the server refused without naming candidates; the screen still has to
   offer the explicit create-anyway path, so `null` and `[]` are different answers. */
export const duplicateMatchesFromProblem = (error: unknown): DuplicateMatch[] | null => {
  if (!(error instanceof ApiProblem) || error.problem.code !== DUPLICATE_ACKNOWLEDGEMENT_REQUIRED) {
    return null;
  }

  const matches = error.problem.context?.matches;

  return Array.isArray(matches) ? matches.filter(isDuplicateMatch) : [];
};

const intakeFingerprint = (intake: ApplicationIntake): string =>
  JSON.stringify([intake.company, intake.target_role, intake.job_text, intake.source_url]);

/* An acknowledgement is an answer about one exact intake, so it may only be sent with
   that same intake. The precheck is asynchronous and the form stays editable while it
   runs, so the text that was answered for and the text about to be created are two
   different values that have to be compared rather than assumed equal. */
export const acknowledgementApplies = (
  answered: ApplicationIntake | undefined,
  current: ApplicationIntake,
): boolean => answered !== undefined && intakeFingerprint(answered) === intakeFingerprint(current);

export const applicationDetailQueryKey = (applicationId: string) =>
  ["application", applicationId] as const;

/* The list query, exactly as the backend defines it.

   `stages` is a list because the endpoint repeats `stage`, and `limit`/`offset` name a
   window on the ordering rather than a slice this client cuts afterwards. Every field is
   optional: an omitted one is the server's default, so the empty query is the whole
   list. */
export interface ApplicationListQuery {
  activity?: ActivityFilter;
  stages?: readonly PreparationState[];
  /* The recruitment axis, beside `stages`. A list for the same reason: the endpoint
     repeats `recruitment_status` once per status. */
  recruitmentStatuses?: readonly RecruitmentStatus[];
  /* One named question the server answers, narrowing alongside the other filters
     rather than replacing them. */
  preset?: ApplicationPreset;
  search?: string;
  sort?: ApplicationSort;
  limit?: number;
  offset?: number;
}

/* The query is part of the key, so two different questions are two cache entries rather
   than one that overwrites the other. Serialized through the same builder that forms the
   request, so a key can never describe a request that was not sent. */
export const applicationListQueryKey = (query: ApplicationListQuery = {}) =>
  ["applications", applicationListSearch(query)] as const;

const applicationsPath: ApiPath = "/api/v1/applications";

const applicationListSearch = (query: ApplicationListQuery): string => {
  const params = new URLSearchParams();

  if (query.activity !== undefined) {
    params.set("activity", query.activity);
  }
  /* Repeated rather than joined: the endpoint takes `stage` once per stage. */
  for (const stage of query.stages ?? []) {
    params.append("stage", stage);
  }
  for (const status of query.recruitmentStatuses ?? []) {
    params.append("recruitment_status", status);
  }
  if (query.preset !== undefined) {
    params.set("preset", query.preset);
  }
  if (query.search !== undefined && query.search !== "") {
    params.set("search", query.search);
  }
  if (query.sort !== undefined) {
    params.set("sort", query.sort);
  }
  if (query.limit !== undefined) {
    params.set("limit", String(query.limit));
  }
  if (query.offset !== undefined && query.offset !== 0) {
    params.set("offset", String(query.offset));
  }

  /* Sorted so two equivalent queries produce one cache key rather than two. */
  params.sort();
  return params.toString();
};

const applicationListPath = (query: ApplicationListQuery): ApiPath => {
  const search = applicationListSearch(query);
  return search === "" ? applicationsPath : `${applicationsPath}?${search}`;
};

const applicationPath = (applicationId: string): ApiPath =>
  `/api/v1/applications/${encodeURIComponent(applicationId)}`;

const analysesPath = (applicationId: string): ApiPath =>
  `/api/v1/applications/${encodeURIComponent(applicationId)}/analyses`;

const generateWorkingDraftPath = (applicationId: string): ApiPath =>
  `/api/v1/applications/${encodeURIComponent(applicationId)}/working-draft/generate`;

/* The one read the application context screen is built on. §9 computes the whole
   projection in one read transaction, so it arrives as one answer and is rendered as
   one; nothing here recombines it into a second view of the same state.

   It refetches on the Operation interval while the projection itself reports live work.
   The condition is the backend's own `is_terminal`, not a status this module reads: an
   Operation that has finished stops the poll, and a projection with no active Operation
   never starts one. */
export const applicationDetailQueryOptions = (applicationId: string) =>
  queryOptions({
    queryKey: applicationDetailQueryKey(applicationId),
    queryFn: async ({ signal }) => {
      const response = await apiRequest<ApplicationDetail>(applicationPath(applicationId), {
        signal,
      });
      return response.data;
    },
    refetchInterval: (query) => {
      const active = query.state.data?.active_operation;
      return active == null || isTerminalOperation(active) ? false : OPERATION_POLL_INTERVAL_MS;
    },
  });

/* Every Application this instance holds, which is what makes an existing one reachable
   again. Without it the only route to a saved Application was its URL, so the root screen
   had to be the intake form and "home" meant starting over.

   It carries the same §9 state projection per row as the detail read, so the list reports
   where each Application actually stands rather than deriving a second opinion from its
   recruitment status.

   Search, filter, and sort are the server's answer, not this client's. They narrow by
   `preparation_state`, which §9 computes from a record's snapshots, drafts, validations,
   and revisions rather than storing on it - a client that filtered or ordered by it would
   be re-deriving state the projection already owns. The query goes out as query
   parameters and the narrowed rows come back with `total`, the count before narrowing,
   so the screen can say how much it is not showing without asking twice.

   It polls on the Operation interval while any row reports live work, on the same
   condition and for the same reason as the detail read: the board shows a running
   Operation per row, and a badge that only moves when the tab is reopened is a worse
   answer than no badge. With every Operation terminal, or none present, nothing polls. */
export const applicationListQueryOptions = (query: ApplicationListQuery = {}) =>
  queryOptions({
    queryKey: applicationListQueryKey(query),
    queryFn: async ({ signal }) => {
      const response = await apiRequest<ApplicationListResponse>(
        applicationListPath(query),
        { signal },
      );
      return response.data;
    },
    refetchInterval: (state) =>
      state.state.data?.items.some(
        (item) => item.active_operation != null && !isTerminalOperation(item.active_operation),
      ) === true
        ? OPERATION_POLL_INTERVAL_MS
        : false,
    /* The board is re-read on every change to the controls. Without this the rows blank
       to a loading line between two answers to nearly the same question, so typing in
       the search field flickered the table once per keystroke. */
    placeholderData: (previous) => previous,
  });

/* §13: the snapshot is named by the caller. An analyze command that picked its own
   source could classify something other than what the user was looking at, so the ID
   comes from the projection the screen is showing rather than from a default.

   Manual Web actions may name `openai` when the effective Settings say AI; otherwise
   `provider` and `model` remain omitted and the server's deterministic defaults keep
   the path reachable with no AI key.
*/
export const startAnalysis = async (
  applicationId: string,
  jobSnapshotId: string,
  idempotencyKey: string,
  provider?: "openai",
): Promise<QueuedOperation> => {
  /* The source is always explicit. Provider is conditional and never spells out the
     deterministic default; the `Pick`s bind both field names to the generated contract. */
  const body: Pick<CreateAnalysisRequest, "job_snapshot_id"> &
    Partial<Pick<CreateAnalysisRequest, "provider">> = {
    job_snapshot_id: jobSnapshotId,
    ...(provider === undefined ? {} : { provider }),
  };

  return queuedOperation(
    await apiRequest<Operation>(analysesPath(applicationId), {
      method: "POST",
      body,
      idempotencyKey,
    }),
  );
};

/* §14 and §21: the no-review continuation. A successful analysis commits the JobAnalysis
   and its initial deterministic SelectionPlan together, which is exactly what lets Draft
   be called with explicit source IDs; both are named by the caller here rather than
   resolved server-side, so a plan the user never saw cannot become the one that is
   drafted from. The Operation freezes them, and a source that moves before activation
   fails as `SOURCE_CHANGED` instead of drafting from something else.

   Manual AI mode may name `openai`; auto-generation deliberately leaves provider absent
   so that path stays deterministic and offline. */
export const startDraftGeneration = async (
  applicationId: string,
  jobAnalysisId: string,
  selectionPlanId: string,
  idempotencyKey: string,
  options: { parentRevisionId?: string; provider?: "openai" } = {},
): Promise<QueuedOperation> => {
  const body: Pick<GenerateWorkingDraftRequest, "job_analysis_id" | "selection_plan_id"> &
    Partial<Pick<GenerateWorkingDraftRequest, "parent_revision_id" | "provider">> = {
    job_analysis_id: jobAnalysisId,
    selection_plan_id: selectionPlanId,
    ...(options.parentRevisionId === undefined
      ? {}
      : { parent_revision_id: options.parentRevisionId }),
    ...(options.provider === undefined ? {} : { provider: options.provider }),
  };

  return queuedOperation(
    await apiRequest<Operation>(generateWorkingDraftPath(applicationId), {
      method: "POST",
      body,
      idempotencyKey,
    }),
  );
};

/* §Tracking: archive one Application without deleting anything.

   It is an append-only status transition, not a delete: the record, its snapshots, and
   every approved revision stay exactly as they are, and the Application keeps its row.
   What changes is which board it appears on - a closed Application is not what a board
   of live work is asking about, so the default list filter stops returning it.

   Not in `available_actions`. That projection answers the preparation workflow, and this
   is the recruitment axis beside it; the one rule this client applies is that an
   Application already closed is not offered closing again. */
export const closeApplication = async (applicationId: string): Promise<ClosedApplication> => {
  const response = await apiRequest<ClosedApplication>(
    `/api/v1/applications/${encodeURIComponent(applicationId)}/close`,
    { method: "POST" },
  );
  return response.data;
};
