import type { QueryClient } from "@tanstack/react-query";

import { createApplication, invalidateApplicationViews, startAnalysis } from "@/api/applications";
import type { ApplicationIntake, Operation } from "@/api/contracts";
import { ApiProblem, type ProblemDetails } from "@/api/client";
import { operationQueryKey } from "@/api/operations";

export interface CreatedIntakeApplication {
  applicationId: string;
  operation: Operation | null;
  analysisProblem: ProblemDetails | null;
  /* True when analysis was not requested because no AI provider can run it. */
  analysisSkipped: boolean;
}

/* Creation is deliberately complete before analysis is requested: if queuing analysis
   fails, the new immutable snapshot still exists and is the destination for recovery.

   With no AI provider the request is not sent at all. Analysis is AI-only, so it could
   only be queued to fail, and the reader would land on a failure report for something
   the intake screen already told them could not run. */
export const createIntakeApplication = async (
  queryClient: QueryClient,
  intake: ApplicationIntake,
  acknowledgedDuplicates: boolean,
  analysisAvailable: boolean,
): Promise<CreatedIntakeApplication> => {
  const created = await createApplication(intake, acknowledgedDuplicates);

  void invalidateApplicationViews(queryClient, created.application_id);

  if (!analysisAvailable) {
    return { applicationId: created.application_id, operation: null, analysisProblem: null, analysisSkipped: true };
  }

  try {
    const { operation } = await startAnalysis(
      created.application_id,
      created.job_snapshot_id,
      `create:${created.application_id}:${created.job_snapshot_id}`,
    );

    /* Seeded here, the same way `useAnalyzeCommand` seeds a re-analysis: the Application
       screen reads this id from route state and finds the record already in cache, so it
       can show the real Operation on first paint instead of a pending placeholder. */
    queryClient.setQueryData(operationQueryKey(operation.id), operation);

    return { applicationId: created.application_id, operation, analysisProblem: null, analysisSkipped: false };
  } catch (error) {
    return {
      applicationId: created.application_id,
      operation: null,
      analysisProblem: error instanceof ApiProblem ? error.problem : null,
      analysisSkipped: false,
    };
  }
};
