import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";

import { invalidateApplicationViews } from "@/api/applications";
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
  /* Only what this screen's own press produced: the announcement and the focus move
     belong to a run the user asked for, not to one read back with the draft. */
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
}

/* A.4 frame 5's command and its result, beside the draft it describes rather than on a
   screen of its own. Every command, key, and staleness rule is the one the standalone
   screen used. */
export const useDraftValidation = (applicationId: string, draft: WorkingDraft | undefined): DraftValidation => {
  const queryClient = useQueryClient();
  const [stale, setStale] = useState(false);

  const runId = draft?.latest_validation_run_id ?? null;
  const runQuery = useQuery({
    ...validationRunQueryOptions(runId ?? ""),
    enabled: runId !== null,
  });

  const validation = useMutation({
    mutationFn: async () => {
      if (draft === undefined) throw new Error("Validation was offered before the draft loaded");
      return validateWorkingDraft(draft.id, draft.edit_version);
    },
    onSuccess: () => {
      void invalidateApplicationViews(queryClient, applicationId);
    },
  });

  const run = validation.data ?? runQuery.data;
  /* §14: approval names an exact version. A run that describes any other draft, edit
     version, or content hash is evidence about a version that no longer exists. */
  const exact =
    run !== undefined &&
    run.passed &&
    draft !== undefined &&
    run.application_id === applicationId &&
    run.working_draft_id === draft.id &&
    run.edit_version === draft.edit_version &&
    run.content_hash === draft.content_hash;

  return {
    canValidate: draft !== undefined,
    error: runQuery.error ?? validation.error,
    exactPassingRunId: exact && run !== undefined ? run.validation_run_id : null,
    isPending: validation.isPending,
    lastRun: validation.data,
    reportStaleRefusal: () => setStale(true),
    run,
    stale,
    validate: () => {
      setStale(false);
      validation.mutate();
    },
  };
};
