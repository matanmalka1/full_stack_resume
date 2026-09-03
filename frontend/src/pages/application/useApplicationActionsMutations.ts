import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";

import {
  applicationDetailQueryKey,
  invalidateApplicationViews,
  replaceWorkingDraft,
  startAnalysis,
  startDraftGeneration,
} from "../../api/applications";
import type { ApplicationDetail } from "../../api/contracts";
import { archiveWorkingDraft, workingDraftQueryKey, workingDraftQueryOptions } from "../../api/drafts";
import { executionProvider } from "../../api/settings";
import { useSettings } from "../../api/useSettings";
import {
  type QueuedOperation,
  isTerminalOperation,
  operationQueryKey,
  operationQueryOptions,
} from "../../api/operations";
import { applicationActionPlan } from "./applicationActionPlan";

/* A.1: the actions come from the projection, read by `applicationActionPlan`. What is left
   here is the mutations this screen sends, and the state that guards when they may be
   sent - everything the panel needs to decide, apart from how it is drawn. */
export const useApplicationActionsMutations = (detail: ApplicationDetail, onQueued: (operationId: string) => void) => {
  const queryClient = useQueryClient();
  const { settings } = useSettings();
  const provider = executionProvider(settings);
  const snapshotId = detail.active_job_snapshot_id;
  const plan = applicationActionPlan(detail);
  /* One key per snapshot: an answer that never arrived can be sent again without
     queueing a second analysis of the same posting. Derived rather than cached, since a
     discarded useMemo would mint a new key on the same snapshot and break that guarantee. */
  const analyzeKey = `analyze:${detail.application.id}:${snapshotId}`;
  /* One key per source pair, for the same reason: a resent generate for the same analysis
     and plan is the same command, and a different pair is a different one. */
  const draftKey = `draft:${plan.createDraft?.analysisId}:${plan.createDraft?.selectionPlanId}`;

  /* Both commands queue durable work and answer `202` with the Operation they queued, so
     both follow it the same way - and neither navigates.

     Queueing used to send the user to the Operation's own screen, which made every action
     a round trip out of the context they were working in and back again. The projection
     carries `active_operation` in full and starts polling the moment it appears, so the
     Application screen reports the work in place. What the accepted `202` still buys is
     the first state: seeding it means the panel appears immediately instead of after the
     next poll, and the Operation screen a direct link reaches is already warm. */
  const followQueued = ({ operation }: QueuedOperation) => {
    queryClient.setQueryData(operationQueryKey(operation.id), operation);
    setQueuedId(operation.id);
    onQueued(operation.id);
    void invalidateApplicationViews(queryClient, detail.application.id);
  };

  const analyze = useMutation({
    mutationFn: () => startAnalysis(detail.application.id, snapshotId, analyzeKey, provider),
    onSuccess: followQueued,
  });

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

  /* Whether durable work is in flight for this Application, and therefore whether the two
     stale-draft commands may be sent at all.

     Neither `isPending` nor the projection answers this alone. `isPending` ends at the
     accepted `202`, which is the moment the work *starts*; the projection reports the
     Operation only on its next read. Between them sits a window in which the screen showed
     two live buttons over a running replacement - long enough to archive the draft that
     replacement was about to write to, or to queue a second one.

     So the locally queued id closes the near end and the projection covers the rest. The
     seeded Operation is read from the cache `followQueued` populates, so the id stops
     counting as in-flight once that record reaches a terminal status rather than staying
     latched until the projection catches up.

     This is a courtesy, not the safety mechanism. Another tab, a reload, or any other
     client can still send a competing command, which is why the engine refuses a
     replacement whose draft moved rather than trusting a disabled button. */
  const [queuedId, setQueuedId] = useState<string | null>(null);
  const queuedOperationQuery = useQuery({
    ...operationQueryOptions(queuedId ?? ""),
    enabled: queuedId !== null,
  });
  const queuedStillRunning = queuedId !== null && !isTerminalOperation(queuedOperationQuery.data);
  const workInFlight = queuedStillRunning || detail.active_operation != null;

  /* The Keep decision is made in the dialog, not assumed by the button. Default on: a
     draft carries manual wording that nothing regenerates, so the reader opts out of
     keeping it rather than having to know to opt in. */
  const [replaceOpen, setReplaceOpen] = useState(false);
  const [keepPrevious, setKeepPrevious] = useState(true);
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

  /* Closing restores the default rather than remembering the last answer. The checkbox is
     a per-replacement decision, and an unchecked box carried over from a cancelled dialog
     would make the next replacement silently discard history the reader never chose to
     discard. */
  const closeReplace = () => {
    setReplaceOpen(false);
    setKeepPrevious(true);
  };

  const replace = useMutation({
    mutationFn: async () => {
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
    onSuccess: (queued) => {
      closeReplace();
      followQueued(queued);
    },
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
    closeReplace,
    commandsBlocked,
    draft,
    editVersion,
    error,
    keepPrevious,
    plan,
    provider,
    replace,
    replaceOpen,
    setKeepPrevious,
    setReplaceOpen,
    settings,
    workInFlight,
  };
};
