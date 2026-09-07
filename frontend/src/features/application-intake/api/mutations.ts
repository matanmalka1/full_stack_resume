import type { QueryClient } from "@tanstack/react-query";

import { createApplication, invalidateApplicationViews, startAnalysis } from "@/api/applications";
import type { ApplicationIntake } from "@/api/contracts";
import { ApiProblem, type ProblemDetails } from "@/api/client";
import { executionProvider, settingsQueryOptions } from "@/api/settings";

export interface CreatedIntakeApplication {
  applicationId: string;
  analysisQueued: boolean;
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
    const { settings } = await queryClient.ensureQueryData(settingsQueryOptions);
    await startAnalysis(
      created.application_id,
      created.job_snapshot_id,
      `create:${created.application_id}:${created.job_snapshot_id}`,
      executionProvider(settings),
    );

    return { applicationId: created.application_id, analysisQueued: true, analysisProblem: null };
  } catch (error) {
    return {
      applicationId: created.application_id,
      analysisQueued: false,
      analysisProblem: error instanceof ApiProblem ? error.problem : null,
    };
  }
};
