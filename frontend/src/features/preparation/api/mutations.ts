import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useCallback, useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";

import { applicationListQueryPrefix, invalidateApplicationViews, startAnalysis } from "@/api/applications";
import type { ApplicationDetail, Operation } from "@/api/contracts";
import { buildFromAnalysis, createDraft, invalidateDocumentViews } from "@/api/documents";
import { type QueuedOperation, isTerminalOperation, operationQueryKey, operationQueryOptions } from "@/api/operations";
import { settingsQueryOptions } from "@/api/settings";
import { useSettings } from "@/features/settings";
import { routePaths } from "@/navigation/routePaths";
import { type AutoDraftSources, autoDraftIsContinuing, autoDraftSources } from "../model/autoDraft";
import { usePreparationContinuation } from "../model/usePreparationContinuation";
import type { WorkflowActionPlan } from "../model/workflowActionPlan";

/* Every command the preparation screen sends, and the guards that say when each may be
   sent. Nothing here holds screen state: the rebuild dialog's confirmation belongs to the
   screen that opens it. */

/* The analyze command on its own, because two surfaces send it and only one of them
   needs anything else. The first analysis of an Application is offered among the
   workflow's next steps; a re-analysis is offered beside the analysis it would replace,
   in the diagnostics tab. Both send this exact command, and reaching it through the full
   command hook mounted the in-flight Operation query a second time for a button that needs
   none of it. */
export const useAnalyzeCommand = (detail: ApplicationDetail, onQueued: (operationId: string) => void) => {
  const queryClient = useQueryClient();
  const { settings } = useSettings();
  const jobTextHash = detail.job_text_hash;
  /* One key per job text and the single analysis lane. */
  const analyzeKey = `analyze:${detail.application.id}:${jobTextHash}:openai`;

  const analyze = useMutation({
    mutationFn: () => startAnalysis(detail.application.id, jobTextHash, analyzeKey),
    /* Queueing does not navigate. The projection carries `active_operation` in full and
       starts polling the moment it appears, so the screen reports the work in place;
       what the accepted `202` buys is the first state, a poll earlier than the
       projection would report it. */
    onSuccess: ({ operation }) => {
      queryClient.setQueryData(operationQueryKey(operation.id), operation);
      onQueued(operation.id);
      void invalidateApplicationViews(queryClient, detail.application.id);
    },
  });

  return { analyze, settings };
};

interface AutomaticDraftAttempt {
  sources: AutoDraftSources;
  triggerOperationId: string;
}

/* Owns the Web automation continuation from a successful analysis to its draft, and the
   move to the editor once any generate this screen queued has succeeded.

   Eligibility comes from two server-backed reads only: the watched analyze Operation and
   the Application projection. The mutation's variables prevent another dispatch of the
   same continuation while this hook is mounted; across reloads, the stable command key
   makes a repeated request the same command at the API boundary.

   History entry state retains only the tab's explicit continuation intent. */
export const useAutomaticDraft = ({
  applicationId,
  detail,
  operation,
  operationId,
  watch,
}: {
  applicationId: string;
  detail: ApplicationDetail | undefined;
  operation: Operation | undefined;
  operationId: string | null;
  watch: (operationId: string) => void;
}) => {
  const queryClient = useQueryClient();
  const navigate = useNavigate();
  const settingsQuery = useQuery(settingsQueryOptions);
  const { intent, mark } = usePreparationContinuation(applicationId);

  /* One auto-draft per document hash, whichever render reaches it first. The source-
     derived idempotency key below is the same guard at the API boundary, for a race this
     ref cannot see across reloads. */
  const dispatchedSourcesRef = useRef<string | null>(null);
  const scopeRef = useRef(applicationId);
  const mountedRef = useRef(true);
  useEffect(() => {
    scopeRef.current = applicationId;
    mountedRef.current = true;
    return () => {
      mountedRef.current = false;
    };
  }, [applicationId]);

  /* The automatic path is the same AI run the button starts, queued without the press. */
  const automaticDraft = useMutation({
    mutationFn: ({ sources }: AutomaticDraftAttempt) =>
      createDraft(sources.applicationId, sources.documentHash, `auto-draft:${sources.documentHash}`),
    onSuccess: ({ operation: queued }, attempt) => {
      queryClient.setQueryData(operationQueryKey(queued.id), queued);
      void queryClient.invalidateQueries({ queryKey: applicationListQueryPrefix });
      if (
        !mountedRef.current ||
        scopeRef.current !== attempt.sources.applicationId ||
        queued.application_id !== scopeRef.current
      )
        return;
      if (!mark({ applicationId: attempt.sources.applicationId, draftOperationId: queued.id })) return;
      watch(queued.id);
    },
  });

  const attemptInScope = automaticDraft.variables?.sources.applicationId === applicationId;
  const attemptedOperationId = attemptInScope ? (automaticDraft.variables?.triggerOperationId ?? null) : null;
  useEffect(() => {
    if (operationId === null || attemptedOperationId === operationId) {
      return;
    }
    const sources = autoDraftSources(operation, settingsQuery.data?.settings, detail);
    if (sources !== null && sources.applicationId === applicationId) {
      const dispatchKey = `${sources.applicationId}:${sources.documentHash}`;
      if (dispatchedSourcesRef.current === dispatchKey) return;
      dispatchedSourcesRef.current = dispatchKey;
      automaticDraft.mutate({ sources, triggerOperationId: operationId });
    }
  }, [applicationId, attemptedOperationId, automaticDraft, detail, operation, operationId, settingsQuery.data]);

  /* A navigation receipt is intent, not proof of activation. Wait until the projection
     reports content for this Application, and never consume another URL's late result. */
  const navigationPending =
    operation?.application_id === applicationId &&
    operation.operation_type === "create_draft" &&
    operation.status === "succeeded" &&
    detail?.application.id === applicationId &&
    detail.application.deleted_at == null &&
    detail.review_reasons.length === 0 &&
    (detail.active_operation == null || detail.active_operation.id === operation.id) &&
    intent?.draftOperationId === operation.id;
  const contentArrived =
    detail !== undefined &&
    detail.preparation_state !== "needs_analysis" &&
    detail.preparation_state !== "ready_to_draft";

  useEffect(() => {
    if (!navigationPending || !contentArrived) return;
    navigate(routePaths.draft(applicationId), { replace: true, state: null });
  }, [applicationId, contentArrived, navigate, navigationPending]);

  /* What the screen reporting this Application's work should say instead of reporting a
     finished run, while this hook is about to start or move to the next one: between a
     succeeded analyze and the generate that follows it, and between a succeeded generate
     and the editor this hook navigates to. In both the Operation overlay must stay open
     rather than close on "הושלמה" and reopen for what comes next.

     A dispatch that failed ends the first: with no continuation coming, the analysis has
     genuinely finished and its run settles like any other. */
  const continuation =
    operation?.status !== "succeeded"
      ? undefined
      : !(attemptInScope && automaticDraft.isError) &&
          ((attemptInScope && automaticDraft.isPending) ||
            autoDraftIsContinuing(operation, settingsQuery.data?.settings, detail))
        ? "הניתוח הושלם. יצירת הטיוטה מתחילה מיד."
        : navigationPending
          ? "הטיוטה נוצרה. מעבר לעורך הטיוטה…"
          : undefined;

  return { continuation };
};

/* A.1: which actions are offered comes from the projection, read by `workflowActionPlan`
   and handed in. What is left here is the commands the preparation screen sends and the
   in-flight guard that says when they may be sent. */
export const useWorkflowCommands = (
  detail: ApplicationDetail,
  plan: WorkflowActionPlan,
  onQueued: (operationId: string) => void,
  /* The screen's own answer, from the watch it keeps: it also covers work this hook did
     not queue - a retry from the run's overlay, the automatic draft - and the moment
     between a success and the refreshed read of what it produced. */
  operationLive: boolean,
) => {
  const queryClient = useQueryClient();
  const { mark } = usePreparationContinuation(detail.application.id);

  /* Whether durable work is in flight for this Application. `isPending` ends at the
     accepted `202`, which is the moment the work *starts*; the projection reports the
     Operation only on its next read. The locally queued id closes that window, read from
     the cache the command populated so it stops counting once the record is terminal.

     This is a courtesy, not the safety mechanism: every command carries the document hash
     it was read with, and the engine refuses one addressed to a document that moved. */
  const [queuedId, setQueuedId] = useState<string | null>(null);
  const follow = useCallback(
    (operationId: string) => {
      setQueuedId(operationId);
      onQueued(operationId);
    },
    [onQueued],
  );

  const { analyze, settings } = useAnalyzeCommand(detail, follow);

  const queuedOperationQuery = useQuery({
    ...operationQueryOptions(queuedId ?? ""),
    enabled: queuedId !== null,
  });
  const queuedStillRunning = queuedId !== null && !isTerminalOperation(queuedOperationQuery.data);
  const workInFlight = operationLive || queuedStillRunning || detail.active_operation != null;

  /* The generate writes the document's content, which is worked on in the editor, so the
     run is registered as one that moves the reader there when it succeeds.
     `useAutomaticDraft`, mounted by the same screen, owns that move. */
  const followQueued = ({ operation }: QueuedOperation) => {
    queryClient.setQueryData(operationQueryKey(operation.id), operation);
    if (!mark({ applicationId: operation.application_id, draftOperationId: operation.id })) return;
    follow(operation.id);
    void invalidateApplicationViews(queryClient, detail.application.id);
  };

  const draft = useMutation({
    mutationFn: async () => {
      /* Availability is the projection's answer, but the hash is this call's argument: a
         generate without it is not a command this screen may send. */
      if (plan.createDraft === null) {
        throw new Error("create_draft was offered without a document to address");
      }
      /* One key per document hash: a resent generate for the same document is the same
         command, and a changed document is a different one. */
      return createDraft(
        detail.application.id,
        plan.createDraft.documentHash,
        `draft:${plan.createDraft.documentHash}`,
      );
    },
    onSuccess: followQueued,
  });

  /* §14 `build_from_analysis`: synchronous, so there is no Operation to follow - only the
     reads whose answer it changed. A refusal because the document moved is reported, and
     the re-read shows the reader what is actually there before they decide again. */
  const rebuild = useMutation({
    mutationFn: async () => {
      if (plan.buildFromAnalysis === null) {
        throw new Error("build_from_analysis was offered without an analysis and a document to address");
      }
      return buildFromAnalysis(
        detail.application.id,
        plan.buildFromAnalysis.documentHash,
        plan.buildFromAnalysis.analysisId,
      );
    },
    onSettled: () => invalidateDocumentViews(queryClient, detail.application.id),
  });

  const commandsBlocked = workInFlight || rebuild.isPending;
  const error = analyze.error ?? draft.error ?? rebuild.error;

  return {
    analyze,
    commandsBlocked,
    draft,
    error,
    rebuild,
    settings,
    workInFlight,
  };
};
