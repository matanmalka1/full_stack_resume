import { type QueryClient, queryOptions } from "@tanstack/react-query";

import { type ApiPath, apiRequest } from "./client";
import type { GapQuestionSet, Operation } from "./contracts";
import { OPERATION_POLL_INTERVAL_MS, type QueuedOperation, queuedOperation } from "./operations";

/* §13a: the questions asked about an Application's unmet requirements, and the commands
   that answer or skip them. Every route is under the Application, so a question is only
   ever reached through the record that owns it. */

const gapQuestionsPath = (applicationId: string): ApiPath =>
  `/api/v1/applications/${encodeURIComponent(applicationId)}/gap-questions`;
const gapQuestionPath = (applicationId: string, questionId: string): ApiPath =>
  `${gapQuestionsPath(applicationId)}/${encodeURIComponent(questionId)}`;

export const gapQuestionsQueryKey = (applicationId: string) => ["gap-questions", applicationId] as const;

/* While any question's fact is being drafted the set is read again on the Operation
   interval: the outcome - a pending fact, or the question back to open - is the set's to
   report, and nothing else on the screen polls for it. */
export const hasDraftInFlight = (set: GapQuestionSet | undefined): boolean =>
  set?.questions.some((question) => question.state === "drafting") === true;

export const gapQuestionsQueryOptions = (applicationId: string) =>
  queryOptions({
    queryKey: gapQuestionsQueryKey(applicationId),
    queryFn: async ({ signal }) => (await apiRequest<GapQuestionSet>(gapQuestionsPath(applicationId), { signal })).data,
    refetchInterval: (query) => (hasDraftInFlight(query.state.data) ? OPERATION_POLL_INTERVAL_MS : false),
  });

export const invalidateGapQuestions = (queryClient: QueryClient, applicationId: string): Promise<void> =>
  queryClient.invalidateQueries({ queryKey: gapQuestionsQueryKey(applicationId) });

export const askGapQuestions = async (
  applicationId: string,
  jobAnalysisId: string,
  idempotencyKey: string,
): Promise<QueuedOperation> =>
  queuedOperation(
    await apiRequest<Operation>(gapQuestionsPath(applicationId), {
      method: "POST",
      body: { job_analysis_id: jobAnalysisId },
      idempotencyKey,
    }),
  );

export const answerGapQuestion = async (
  applicationId: string,
  questionId: string,
  answer: string,
  idempotencyKey: string,
): Promise<QueuedOperation> =>
  queuedOperation(
    await apiRequest<Operation>(`${gapQuestionPath(applicationId, questionId)}/answer` as ApiPath, {
      method: "POST",
      body: { answer },
      idempotencyKey,
    }),
  );

export const skipGapQuestion = async (applicationId: string, questionId: string): Promise<GapQuestionSet> =>
  (
    await apiRequest<GapQuestionSet>(`${gapQuestionPath(applicationId, questionId)}/skip` as ApiPath, {
      method: "POST",
    })
  ).data;
