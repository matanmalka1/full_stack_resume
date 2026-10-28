import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect } from "react";

import { invalidateApplicationViews } from "@/api/applications";
import type { ConfirmAndUseFactRequest, EditPendingFactRequest } from "@/api/contracts";
import { invalidateDocumentViews } from "@/api/documents";
import { confirmAndUseFact, confirmFact, editPendingFact, invalidateFactViews } from "@/api/facts";
import {
  answerGapQuestion,
  askGapQuestions,
  gapQuestionsQueryKey,
  gapQuestionsQueryOptions,
  invalidateGapQuestions,
  skipGapQuestion,
} from "@/api/gapQuestions";
import { type QueuedOperation, isTerminalOperation, operationQueryKey, operationQueryOptions } from "@/api/operations";

/* The gap-question commands of the analysis step (§13a) and what each one moves.

   Asking and answering are Operations. Both are reported by the step's own Operation
   overlay, which opens on the projection's `active_operation`, so a queued one refreshes
   the projection; the question set is read again once the work it waits on has ended. */

export const useGapQuestions = (applicationId: string, enabled: boolean) =>
  useQuery({ ...gapQuestionsQueryOptions(applicationId), enabled });

/* The question set exists only once the ask has succeeded, so it is read again when the
   run this step is following ends - whatever the outcome, the set is what says it. */
export const useRefreshOnSettled = (applicationId: string, operationId: string | null) => {
  const queryClient = useQueryClient();
  const operation = useQuery({ ...operationQueryOptions(operationId ?? ""), enabled: operationId !== null });
  const finished = operationId !== null && isTerminalOperation(operation.data);
  useEffect(() => {
    if (finished) void invalidateGapQuestions(queryClient, applicationId);
  }, [applicationId, finished, queryClient]);
  return { live: operationId !== null && !finished };
};

const useFollowQueued = (applicationId: string) => {
  const queryClient = useQueryClient();
  return ({ operation }: QueuedOperation) => {
    queryClient.setQueryData(operationQueryKey(operation.id), operation);
    void invalidateApplicationViews(queryClient, applicationId);
    void invalidateGapQuestions(queryClient, applicationId);
  };
};

export const useAskGapQuestions = (applicationId: string, analysisId: string | null) => {
  const follow = useFollowQueued(applicationId);
  return useMutation({
    mutationFn: () => {
      if (analysisId === null) throw new Error("ask_gap_questions was offered without an analysis");
      /* One key per analysis: asking twice about the same analysis is the same command,
         and a failed run is retried from its report rather than resent from here. */
      return askGapQuestions(applicationId, analysisId, `gap-questions:${analysisId}`);
    },
    onSuccess: follow,
  });
};

export const useAnswerGapQuestion = (applicationId: string, questionId: string, lastDraftId: string | null) => {
  const follow = useFollowQueued(applicationId);
  return useMutation({
    /* One key per attempt: an answer resent after a refused draft is a new command, and
       the refused draft's id is what separates it from the one before. */
    mutationFn: (answer: string) =>
      answerGapQuestion(applicationId, questionId, answer, `gap-answer:${questionId}:${lastDraftId ?? "first"}`),
    onSuccess: follow,
  });
};

export const useSkipGapQuestion = (applicationId: string, questionId: string) => {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: () => skipGapQuestion(applicationId, questionId),
    onSuccess: (set) => queryClient.setQueryData(gapQuestionsQueryKey(applicationId), set),
  });
};

/* A fact write moves the knowledge store and the question that shows the fact. */
const useFactRefresh = (applicationId: string, factId: string) => {
  const queryClient = useQueryClient();
  return () => {
    invalidateFactViews(queryClient, factId);
    void invalidateGapQuestions(queryClient, applicationId);
  };
};

export const useEditGapFact = (applicationId: string, factId: string, onSaved: () => void) => {
  const refresh = useFactRefresh(applicationId, factId);
  return useMutation({
    mutationFn: (changes: Omit<EditPendingFactRequest, "reason">) =>
      editPendingFact(factId, { ...changes, reason: "edited from a gap question answer" }),
    onSuccess: () => {
      refresh();
      onSaved();
    },
  });
};

export const useConfirmGapFact = (applicationId: string, factId: string) => {
  const refresh = useFactRefresh(applicationId, factId);
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: () => confirmFact(factId, { confirm: true, reason: "confirmed from a gap question answer" }),
    onSuccess: () => {
      refresh();
      void invalidateApplicationViews(queryClient, applicationId);
    },
  });
};

/* Confirms and attaches in one command (§17): the document and its projection move with
   the Profile's pool, so both are read again. */
export const useConfirmAndUseGapFact = (applicationId: string, factId: string) => {
  const refresh = useFactRefresh(applicationId, factId);
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (target: Pick<ConfirmAndUseFactRequest, "job_analysis_id" | "profile" | "section">) =>
      confirmAndUseFact(factId, {
        ...target,
        application_id: applicationId,
        reason: "confirmed and used from a gap question answer",
      }),
    onSuccess: () => {
      refresh();
      void invalidateDocumentViews(queryClient, applicationId);
    },
  });
};
