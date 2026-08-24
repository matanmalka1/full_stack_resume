import { ApiProblem, apiRequest } from "./client";
import type {
  ApplicationIntake,
  CreateApplicationRequest,
  CreatedApplication,
  DuplicateCheckResult,
  DuplicateMatch,
} from "./contracts";

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
    candidate.matched_on.every((reason) => typeof reason === "string")
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
