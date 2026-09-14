import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";

import { applicationDetailQueryOptions, invalidateApplicationViews } from "@/api/applications";
import { workingDraftQueryOptions } from "@/api/drafts";
import type { ValidationRun, WorkingDraft } from "@/api/contracts";
import { validateWorkingDraft, validationRunQueryOptions } from "@/api/validation";

export interface DraftValidation {
  /* False until a draft version exists to validate. */
  canValidate: boolean;
  error: unknown;
  /* The exact passing run's id, or null. Derived from the run and the draft on every
     render rather than reported upward through an effect: approval is offered for this
     value alone, and a copy kept in state could name a version that has since moved. */
  exactPassingRunId: string | null;
  isPending: boolean;
  /* The exact result produced by this screen, including contextual fact follow-up. */
  lastRun: ValidationRun | undefined;
  /* An approval was refused as `VALIDATION_STALE`: the backend judged the run this
     screen offered as evidence to be about a version the draft has moved past. It is
     reported rather than derived - the client's own exactness comparison said the run
     matched, or approval would not have been offered at all. */
  reportStaleRefusal: () => void;
  run: ValidationRun | undefined;
  /* True while that refusal stands. Running a new validation is the answer to it, so
     that is what clears it. */
  stale: boolean;
  validate: () => void;
  validateExact: (current: WorkingDraft) => Promise<ValidationRun>;
}

/* A.4 frame 5's command and its result, beside the draft it describes rather than on a
   screen of its own. Every command, key, and staleness rule is the one the standalone
   screen used. */
export const useDraftValidation = (
  applicationId: string,
  draft: WorkingDraft | undefined,
  unavailable = false,
): DraftValidation => {
  const queryClient = useQueryClient();
  const [stale, setStale] = useState(false);

  const runId = draft?.latest_validation_run_id ?? null;
  const runQuery = useQuery({
    ...validationRunQueryOptions(runId ?? ""),
    enabled: runId !== null,
  });

  const validation = useMutation({
    mutationFn: async (current: WorkingDraft) => {
      return validateWorkingDraft(current.id, current.edit_version);
    },
    onSuccess: async (_run, current) => {
      await invalidateApplicationViews(queryClient, applicationId);
      await Promise.all([
        queryClient.fetchQuery({ ...workingDraftQueryOptions(current.id), staleTime: 0 }),
        queryClient.fetchQuery({ ...applicationDetailQueryOptions(applicationId), staleTime: 0 }),
      ]);
    },
  });

  // Late results cannot describe a newer edit. Prefer the current queried evidence
  // over a response retained from a previous validation request.
  const matches = (run: ValidationRun | undefined) =>
    run !== undefined &&
    draft !== undefined &&
    run.application_id === applicationId &&
    run.working_draft_id === draft.id &&
    run.edit_version === draft.edit_version &&
    run.content_hash === draft.content_hash;
  const candidate = matches(runQuery.data) ? runQuery.data : matches(validation.data) ? validation.data : undefined;
  const run = unavailable ? undefined : candidate;
  const exact = run?.passed === true;

  return {
    canValidate: draft !== undefined && !unavailable && !validation.isPending,
    error: runQuery.error ?? validation.error,
    exactPassingRunId: exact && run !== undefined ? run.validation_run_id : null,
    isPending: validation.isPending,
    lastRun:
      run !== undefined && run.validation_run_id === validation.data?.validation_run_id ? validation.data : undefined,
    reportStaleRefusal: () => setStale(true),
    run,
    stale,
    validate: () => {
      if (draft === undefined || unavailable) return;
      setStale(false);
      validation.mutate(draft);
    },
    validateExact: (current) => {
      setStale(false);
      return validation.mutateAsync(current);
    },
  };
};
