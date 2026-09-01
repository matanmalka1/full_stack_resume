import { queryOptions } from "@tanstack/react-query";

import { type ApiPath, apiRequest } from "./client";
import type {
  Approval,
  ApproveDraftRequest,
  ValidationRun,
  ValidationRunDetail,
  WorkingDraftVersionRequest,
} from "./contracts";

const draftPath = (workingDraftId: string): ApiPath => `/api/v1/working-drafts/${encodeURIComponent(workingDraftId)}`;

const validationRunQueryKey = (validationRunId: string) => ["validation-run", validationRunId] as const;

export const validationRunQueryOptions = (validationRunId: string) =>
  queryOptions({
    queryKey: validationRunQueryKey(validationRunId),
    queryFn: async ({ signal }) => {
      const response = await apiRequest<ValidationRunDetail>(
        `/api/v1/validation-runs/${encodeURIComponent(validationRunId)}`,
        { signal },
      );
      return response.data;
    },
  });

export const validateWorkingDraft = async (
  workingDraftId: string,
  expectedEditVersion: number,
): Promise<ValidationRun> => {
  const body: WorkingDraftVersionRequest = { expected_edit_version: expectedEditVersion };
  const response = await apiRequest<ValidationRun>(`${draftPath(workingDraftId)}/validate` as ApiPath, {
    method: "POST",
    body,
  });
  return response.data;
};

export const approveWorkingDraft = async (
  workingDraftId: string,
  expectedEditVersion: number,
  validationRunId: string,
  idempotencyKey: string,
): Promise<Approval> => {
  const body: ApproveDraftRequest = {
    expected_edit_version: expectedEditVersion,
    validation_run_id: validationRunId,
  };
  const response = await apiRequest<Approval>(`${draftPath(workingDraftId)}/approve` as ApiPath, {
    method: "POST",
    body,
    idempotencyKey,
  });
  return response.data;
};
