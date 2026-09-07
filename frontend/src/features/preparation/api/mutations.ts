import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useCallback, useEffect, useState } from "react";

import {
  applicationDetailQueryKey,
  invalidateApplicationViews,
  replaceWorkingDraft,
  startAnalysis,
  startDraftGeneration,
} from "@/api/applications";
import type { ApplicationDetail, Operation } from "@/api/contracts";
import { archiveWorkingDraft, workingDraftQueryKey, workingDraftQueryOptions } from "@/api/drafts";
import { type QueuedOperation, isTerminalOperation, operationQueryKey, operationQueryOptions } from "@/api/operations";
import { executionProvider, settingsQueryOptions } from "@/api/settings";
import { useSettings } from "@/api/useSettings";
import { type AutoDraftSources, autoDraftSources } from "../model/autoDraft";
import type { WorkflowActionPlan } from "../model/workflowActionPlan";

/* Every command the preparation screen sends, and the guards that say when each may be
   sent. Nothing here holds screen state: the replace dialog's own decision belongs to
   the screen that opens it and reaches the command as an argument. */

/* The analyze command on its own, because two surfaces send it and only one of them
   needs anything else. The first analysis of an Application is offered among the
   workflow's next steps; a re-analysis is offered beside the analysis it would replace,
   in the diagnostics tab. Both send this exact command, and reaching it through the full
   command hook mounted the stale-draft version read and the in-flight Operation query a
   second time for a button that needs neither. */
export const useAnalyzeCommand = (detail: ApplicationDetail, onQueued: (operationId: string) => void) => {
  const queryClient = useQueryClient();
  const { settings } = useSettings();
  const provider = executionProvider(settings);
  const snapshotId = detail.active_job_snapshot_id;
  /* One key per snapshot: an answer that never arrived can be sent again without
     queueing a second analysis of the same posting. Derived rather than cached, since a
     discarded useMemo would mint a new key on the same snapshot and break that
     guarantee. */
  const analyzeKey = `analyze:${detail.application.id}:${snapshotId}`;

  const analyze = useMutation({
    mutationFn: () => startAnalysis(detail.application.id, snapshotId, analyzeKey, provider),
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

  return { analyze, provider, settings };
};

const autoDraftReceiptKey = (operationId: string): string => `stage-e:auto-draft:${operationId}`;

interface AutomaticDraftAttempt {
  sources: AutoDraftSources;
  triggerOperationId: string;
}

/* Owns the Web automation continuation from a successful analysis to its draft.

   Eligibility comes from two server-backed reads only: the watched analyze Operation and
   the Application projection. The mutation's variables prevent another dispatch of the
   same continuation while this hook is mounted; across reloads, the stable command key
   makes a repeated request the same command at the API boundary.

   The session entry is a success receipt retained for the existing screen contract. It is
   deliberately write-only here: it no longer participates in deciding whether work may
   start, so it cannot disagree with the projection or the watched Operation. */
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
  const settingsQuery = useQuery(settingsQueryOptions);
  const automaticDraft = useMutation({
    mutationFn: ({ sources, triggerOperationId }: AutomaticDraftAttempt) =>
      startDraftGeneration(
        sources.applicationId,
        sources.analysisId,
        sources.planId,
        `auto-draft:${triggerOperationId}:${sources.analysisId}:${sources.planId}`,
      ),
    onSuccess: ({ operation: queued }, attempt) => {
      sessionStorage.setItem(autoDraftReceiptKey(attempt.triggerOperationId), "accepted");
      queryClient.setQueryData(operationQueryKey(queued.id), queued);
      watch(queued.id);
      void invalidateApplicationViews(queryClient, applicationId);
    },
  });

  const attemptedOperationId = automaticDraft.variables?.triggerOperationId ?? null;
  useEffect(() => {
    if (operationId === null || attemptedOperationId === operationId) {
      return;
    }
    const sources = autoDraftSources(operation, settingsQuery.data?.settings, detail);
    if (sources !== null) {
      automaticDraft.mutate({ sources, triggerOperationId: operationId });
    }
  }, [attemptedOperationId, detail, operation, operationId, settingsQuery.data]);
};

/* A.1: which actions are offered comes from the projection, read by `workflowActionPlan`
   and handed in. What is left here is the commands the preparation screen sends and the
   in-flight guard that says when they may be sent.

   No screen state: the replace dialog's own decision belongs to the screen that opens it
   and reaches the command as an argument, which is what keeps this a module of commands
   rather than a hook holding half a dialog. */
export const useWorkflowCommands = (
  detail: ApplicationDetail,
  plan: WorkflowActionPlan,
  onQueued: (operationId: string) => void,
) => {
  const queryClient = useQueryClient();

  /* Whether durable work is in flight for this Application, and therefore whether the
     two stale-draft commands may be sent at all.

     Neither `isPending` nor the projection answers this alone. `isPending` ends at the
     accepted `202`, which is the moment the work *starts*; the projection reports the
     Operation only on its next read. Between them sits a window in which the screen
     showed two live buttons over a running replacement - long enough to archive the
     draft that replacement was about to write to, or to queue a second one.

     So the locally queued id closes the near end and the projection covers the rest. The
     seeded Operation is read from the cache the command populated, so the id stops
     counting as in-flight once that record reaches a terminal status rather than staying
     latched until the projection catches up.

     This is a courtesy, not the safety mechanism. Another tab, a reload, or any other
     client can still send a competing command, which is why the engine refuses a
     replacement whose draft moved rather than trusting a disabled button. */
  const [queuedId, setQueuedId] = useState<string | null>(null);
  const follow = useCallback(
    (operationId: string) => {
      setQueuedId(operationId);
      onQueued(operationId);
    },
    [onQueued],
  );

  const { analyze, provider, settings } = useAnalyzeCommand(detail, follow);

  const followQueued = ({ operation }: QueuedOperation) => {
    queryClient.setQueryData(operationQueryKey(operation.id), operation);
    follow(operation.id);
    void invalidateApplicationViews(queryClient, detail.application.id);
  };

  /* One key per source pair: a resent generate for the same analysis and plan is the
     same command, and a different pair is a different one. */
  const draftKey = `draft:${plan.createDraft?.analysisId}:${plan.createDraft?.selectionPlanId}`;

  /* §14: the version the two stale-draft commands are addressed to.

     `expected_edit_version` is optimistic concurrency, and it only does that job if it
     comes from a read of the draft itself - the projection carries the draft's id but not
     its version. Conditional, so an Application with nothing to replace opens no second
     request, and shared with the editor's own read through one cache key.

     Read on view rather than on press deliberately: fetching it inside the command would
     make the guard describe the instant of sending rather than what the reader was looking
     at, and a draft edited in another tab would be overwritten instead of refused. */
  const staleDraftId = plan.replaceDraft?.workingDraftId ?? plan.archiveDraft?.workingDraftId ?? null;
  const staleDraftQuery = useQuery({
    ...workingDraftQueryOptions(staleDraftId ?? ""),
    enabled: staleDraftId !== null,
  });
  const editVersion = staleDraftQuery.data?.draft.edit_version ?? null;

  const queuedOperationQuery = useQuery({
    ...operationQueryOptions(queuedId ?? ""),
    enabled: queuedId !== null,
  });
  const queuedStillRunning = queuedId !== null && !isTerminalOperation(queuedOperationQuery.data);
  const workInFlight = queuedStillRunning || detail.active_operation != null;

  /* One key per replaced version: a resent answer for the same version is the same
     command, and a new version is a different one. */
  const replaceKey = `replace:${staleDraftId}:${editVersion}`;

  const draft = useMutation({
    mutationFn: async () => {
      /* Availability is the projection's answer, but the IDs are this call's arguments:
         a generate without both of them is not a command this screen may send. */
      if (plan.createDraft === null) {
        throw new Error("create_draft was offered without an active analysis and selection plan");
      }
      return startDraftGeneration(
        detail.application.id,
        plan.createDraft.analysisId,
        plan.createDraft.selectionPlanId,
        draftKey,
        { provider },
      );
    },
    onSuccess: followQueued,
  });

  /* A stale version is the guard doing its job, not a failure to retry: the draft moved
     since this screen read it, so the answer is to show the conflict and re-read, and let
     the reader decide again against what is actually there. `retry: false` on mutations is
     the standing policy (§8.6); this adds the re-read. */
  const onVersionConflict = () => {
    if (staleDraftId !== null) {
      void queryClient.invalidateQueries({ queryKey: workingDraftQueryKey(staleDraftId) });
    }
    void queryClient.invalidateQueries({ queryKey: applicationDetailQueryKey(detail.application.id) });
  };

  /* The Keep decision arrives with the press rather than being read from state here: it
     is the dialog's answer, and the dialog is the screen's, so the command takes it as
     the argument it is. */
  const replace = useMutation({
    mutationFn: async ({ keepPrevious }: { keepPrevious: boolean }) => {
      /* Availability is the projection's answer, the version is this call's argument, and
         a replacement without either is not a command this screen may send. */
      if (plan.replaceDraft === null || editVersion === null) {
        throw new Error("replace_working_draft was offered without a draft version to address");
      }
      return replaceWorkingDraft(
        detail.application.id,
        {
          expectedEditVersion: editVersion,
          jobAnalysisId: plan.replaceDraft.analysisId,
          keepPrevious,
          selectionPlanId: plan.replaceDraft.selectionPlanId,
          workingDraftId: plan.replaceDraft.workingDraftId,
        },
        replaceKey,
        { provider },
      );
    },
    onError: onVersionConflict,
    onSuccess: followQueued,
  });

  /* Synchronous, so there is no Operation to follow - only the caches whose answer it
     changed: the draft it archived, and the projection that named it active. */
  const archive = useMutation({
    mutationFn: async () => {
      if (plan.archiveDraft === null || editVersion === null) {
        throw new Error("archive_working_draft was offered without a draft version to address");
      }
      return archiveWorkingDraft(plan.archiveDraft.workingDraftId, editVersion);
    },
    onError: onVersionConflict,
    onSuccess: () => {
      onVersionConflict();
    },
  });

  /* What actually holds the two stale-draft commands.

     `workInFlight` covers durable work - an Operation queued here or reported by the
     projection. Archiving is neither: it is synchronous, so it creates no Operation and
     nothing above would notice it was running. Between its press and its answer both
     buttons stayed live, which is the same competing-command window in miniature: long
     enough to send a replacement addressed to a draft that is being archived. The two
     in-flight mutations close it. */
  const commandsBlocked = workInFlight || archive.isPending || replace.isPending;

  const error = staleDraftQuery.error ?? analyze.error ?? draft.error ?? replace.error ?? archive.error;

  return {
    analyze,
    archive,
    commandsBlocked,
    draft,
    editVersion,
    error,
    provider,
    replace,
    settings,
    workInFlight,
  };
};
