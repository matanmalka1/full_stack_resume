import { queryOptions } from "@tanstack/react-query";

import { ApiProblem, type ApiPath, apiRequest } from "./client";
import type {
  ApplicationDetail,
  ApplicationIntake,
  CreateAnalysisRequest,
  CreateApplicationRequest,
  CreatedApplication,
  DuplicateCheckResult,
  DuplicateMatch,
  DuplicateMatchReason,
  Operation,
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

const applicationPath = (applicationId: string): ApiPath =>
  `/api/v1/applications/${encodeURIComponent(applicationId)}`;

const analysesPath = (applicationId: string): ApiPath =>
  `/api/v1/applications/${encodeURIComponent(applicationId)}/analyses`;

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

/* §13: the snapshot is named by the caller. An analyze command that picked its own
   source could classify something other than what the user was looking at, so the ID
   comes from the projection the screen is showing rather than from a default.

   The request sends nothing else. `provider` and `model` default to `deterministic` and
   `rules-v1` server-side, which is what keeps this path reachable with no AI key; the
   overrides belong to the review form, not to starting an analysis.
*/
export const startAnalysis = async (
  applicationId: string,
  jobSnapshotId: string,
  idempotencyKey: string,
): Promise<QueuedOperation> => {
  /* Only the source. `provider` and `model` are omitted rather than sent as
     `deterministic`/`rules-v1`: those are the server's defaults, and spelling them here
     would be a second copy of a policy this client does not own. The `Pick` still binds
     the field name to the generated request contract. */
  const body: Pick<CreateAnalysisRequest, "job_snapshot_id"> = {
    job_snapshot_id: jobSnapshotId,
  };

  return queuedOperation(
    await apiRequest<Operation>(analysesPath(applicationId), {
      method: "POST",
      body,
      idempotencyKey,
    }),
  );
};
