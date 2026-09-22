import type { QueryClient } from "@tanstack/react-query";

import { createApplication, invalidateApplicationViews, startAnalysis } from "@/api/applications";
import type { ApplicationIntake, Operation } from "@/api/contracts";
import { ApiProblem, type ProblemDetails } from "@/api/client";
import { operationQueryKey } from "@/api/operations";

export interface CreatedIntakeApplication {
  applicationId: string;
  operation: Operation | null;
  analysisProblem: ProblemDetails | null;
}

/* Creation is deliberately complete before analysis is requested: if queuing analysis
   fails, the new immutable snapshot still exists and is the destination for recovery. */
export const createIntakeApplication = async (
  queryClient: QueryClient,
  intake: ApplicationIntake,
  acknowledgedDuplicates: boolean,
): Promise<CreatedIntakeApplication> => {
  const created = await createApplication(intake, acknowledgedDuplicates);

  void invalidateApplicationViews(queryClient, created.application_id);

  try {
    const { operation } = await startAnalysis(
      created.application_id,
      created.job_snapshot_id,
      `create:${created.application_id}:${created.job_snapshot_id}`,
    );

    /* Seeded here, the same way `useAnalyzeCommand` seeds a re-analysis: the Application
       screen reads this id from route state and finds the record already in cache, so it
       can show the real Operation panel on first paint instead of a placeholder card. */
    queryClient.setQueryData(operationQueryKey(operation.id), operation);

    return { applicationId: created.application_id, operation, analysisProblem: null };
  } catch (error) {
    return {
      applicationId: created.application_id,
      operation: null,
      analysisProblem: error instanceof ApiProblem ? error.problem : null,
    };
  }
};
