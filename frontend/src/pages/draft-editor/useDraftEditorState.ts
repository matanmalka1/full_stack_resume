import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useCallback, useState } from "react";

import { applicationDetailQueryKey, applicationDetailQueryOptions } from "../../api/applications";
import type { ApplicationDetail, DraftClaim, DraftFact, WorkingDraftUpdate } from "../../api/contracts";
import {
  type DraftRead,
  applySelectionChange,
  regenerateClaim,
  regenerateSection,
  selectionOverlay,
  workingDraftFactsQueryKey,
  workingDraftFactsQueryOptions,
  workingDraftQueryKey,
  workingDraftQueryOptions,
} from "../../api/drafts";
import { type QueuedOperation, operationQueryKey } from "../../api/operations";
import { aiRegenerationAvailable } from "../../api/settings";
import { useSettings } from "../../api/useSettings";
import { useWorkflowStage, workflowDestinations } from "../../app/WorkflowLandmark";
import { useWatchedOperation } from "../../hooks/useWatchedOperation";
import { removability } from "./claimRemoval";
import { useDraftAutosave } from "./useDraftAutosave";

/* A.4 frame 3: the editor pane's data and commands, apart from how they are drawn. It
   reads the §9 projection for which draft is active and what is blocking, and the draft
   itself for the structure it edits. It derives no second workflow state machine (A.1):
   the blockers are the projection's own review reasons, and approval is refused by the
   backend, not by a rule invented here. */
export const useDraftEditorState = (applicationId: string) => {
  const applicationQuery = useQuery(applicationDetailQueryOptions(applicationId));
  const { isPending: settingsPending, settings } = useSettings();
  const regenerationAvailable = aiRegenerationAvailable(settings);
  const detail: ApplicationDetail | undefined = applicationQuery.data;
  useWorkflowStage(
    detail === undefined ? "unknown" : detail.preparation_state,
    workflowDestinations(applicationId, detail),
  );
  /* The same watch the Application screen keeps, on the other screen that queues durable
     work against one Application. Regeneration is reported here, beside the draft it is
     rewriting. */
  const { panel: operationPanel, watch } = useWatchedOperation(applicationId, detail);

  const workingDraftId = detail?.active_working_draft_id ?? null;
  const draftQuery = useQuery({
    ...workingDraftQueryOptions(workingDraftId ?? ""),
    enabled: workingDraftId !== null,
  });
  const factsQuery = useQuery({
    ...workingDraftFactsQueryOptions(workingDraftId ?? ""),
    enabled: workingDraftId !== null,
  });

  const draft = draftQuery.data?.draft;
  const facts = factsQuery.data;
  const queryClient = useQueryClient();
  /* The three screens that used to follow the editor are states of this one editor.
     None of them changes what is sent: the validation panel runs the same command, the
     dialog is A.4 frame 5's own approval dialog, and the render panel keeps rendering an
     explicit action on the exact revision the approval returned. */
  const [approvalOpen, setApprovalOpen] = useState(false);
  const [validationStale, setValidationStale] = useState(false);
  const [exactPassingRunId, setExactPassingRunId] = useState<string | null>(null);
  /* The revision this editor just approved. Held here rather than read from the
     projection so the render step names the exact revision the approval returned. */
  const [approvedRevisionId, setApprovedRevisionId] = useState<string | null>(null);
  /* Approval deactivates the WorkingDraft atomically. Prefer the exact command response;
     after a reload, the projection may recover the same pending render step only when
     there is no newer active draft and the latest approved revision is the current
     preparation milestone. */
  const renderRevisionId =
    approvedRevisionId ??
    (workingDraftId === null && detail?.preparation_state === "approved"
      ? (detail.latest_approved_revision_id ?? null)
      : null);

  /* A save changes the draft, so the read that produced it is stale by definition. The
     new token is installed directly - it is the one the response returned for the version
     that now exists - and the reads are invalidated so the outline, the pending claims,
     and the projection's blockers all come back describing the same version. */
  const onSaved = useCallback(
    (_update: WorkingDraftUpdate, etag: string | null) => {
      if (workingDraftId === null) {
        return;
      }
      queryClient.setQueryData<DraftRead>(workingDraftQueryKey(workingDraftId), (previous) =>
        previous === undefined ? previous : { ...previous, etag },
      );
      void queryClient.invalidateQueries({
        queryKey: workingDraftQueryKey(workingDraftId),
      });
      void queryClient.invalidateQueries({
        queryKey: workingDraftFactsQueryKey(workingDraftId),
      });
      void queryClient.invalidateQueries({
        queryKey: applicationDetailQueryKey(applicationId),
      });
    },
    [applicationId, queryClient, workingDraftId],
  );

  /* A 409 says the read behind both the editor and its ETag is obsolete. Refresh them as
     one DraftRead so the conflict comparison and the next If-Match name the same server
     version. `fetchQuery` is deliberate here: invalidation alone would not wait for or
     return the replacement token. */
  const refreshConflictedDraft = useCallback(async () => {
    if (workingDraftId === null) {
      return null;
    }
    const current = await queryClient.fetchQuery(workingDraftQueryOptions(workingDraftId));
    return current.etag;
  }, [queryClient, workingDraftId]);

  /* Stable, because the panel reports through it from an effect: a fresh function each
     render would make that effect re-run on every render of this screen. */
  const onExactPassingRun = useCallback((runId: string | null) => {
    setExactPassingRunId(runId);
    /* A fresh exact passing run is the answer to the staleness the approval reported. */
    if (runId !== null) {
      setValidationStale(false);
    }
  }, []);

  const autosave = useDraftAutosave({
    etag: draftQuery.data?.etag ?? null,
    onConflict: refreshConflictedDraft,
    onSaved,
    workingDraftId,
  });

  /* The fact links are the claim's own. An edit changes wording, not what backs it -
     relinking is a separate decision, and sending a different set here would silently
     re-authorize a line the user only rephrased. */
  const editClaim = (claim: DraftClaim, text: string) =>
    autosave.queueEdit({
      claim_id: claim.claim_id,
      fact_ids: claim.fact_ids,
      text,
    });

  /* §14: the overlay is absolute, so every change starts from what the accounting
     currently reports and adds one decision to it. Sending only what moved would drop
     every pin and exclusion the user made before. */
  const selection = useMutation({
    mutationFn: async (change: { pinned?: string[]; excluded?: string[] }) => {
      if (draft === undefined || facts === undefined) {
        throw new Error("a selection change was offered before the draft and its facts arrived");
      }
      const overlay = selectionOverlay(facts);
      return applySelectionChange(draft.id, draft.edit_version, {
        pinned_fact_ids: [...new Set([...overlay.pinned_fact_ids, ...(change.pinned ?? [])])],
        excluded_fact_ids: [...new Set([...overlay.excluded_fact_ids, ...(change.excluded ?? [])])],
      });
    },
    onSuccess: () => {
      /* The plan and the document changed together, and the ETag with them. Nothing from
         the response is seeded: the refreshed reads report the version that now exists. */
      onSaved({} as WorkingDraftUpdate, null);
    },
  });

  /* Which command removes a line is `removability`'s answer, not a guess made here: the
     patch takes the unauthorized claims, and a fact-authorized one is removed by
     excluding the facts behind it. */
  const removeClaim = (claim: DraftClaim) => {
    if (draft === undefined) {
      return;
    }
    const route = removability(claim, draft, facts).route;

    if (route === "patch") {
      autosave.queueRemoval(claim.claim_id);
    }
    if (route === "selection") {
      selection.mutate({ excluded: claim.fact_ids });
    }
  };

  /* Including an omitted fact is a pin: in a budgeted deterministic selection, holding it
     is the only way to say "keep this one". */
  const includeFact = (fact: DraftFact) => selection.mutate({ pinned: [fact.fact_id] });

  /* §14 regeneration is an Operation, and it is reported in place rather than followed to
     a screen of its own.

     It used to navigate. That made the one action that acts on a single line of the draft
     the only action that took the draft off the screen: the user regenerated a claim, was
     handed a progress line with no text beside it, and came back through a link that led
     to the Application screen rather than to the editor they had left. The Application
     screen already reports its own work this way, and this is the same watch - the
     projection opens it, the Operation's own query closes it, and the accepted `202`
     seeds the first state so the panel appears with the press rather than a poll later.

     `/operations/:id` stays reachable: the panel links to it, and it is where a direct
     link or a reload of a queued Operation lands. */
  const followQueued = ({ operation }: QueuedOperation) => {
    queryClient.setQueryData(operationQueryKey(operation.id), operation);
    watch(operation.id);
  };

  const regeneration = useMutation({
    mutationFn: async (target: { claimId?: string; section?: string }) => {
      if (draft === undefined) {
        throw new Error("a regeneration was offered before the draft arrived");
      }
      /* One key per target and version: a resent regeneration of the same line at the
         same version is the same command, and a different version is a different one. */
      const key = `${draft.id}:${draft.edit_version}:${target.claimId ?? target.section ?? ""}`;

      return target.claimId === undefined
        ? regenerateSection(draft, target.section ?? "", key)
        : regenerateClaim(draft, target.claimId, key);
    },
    onSuccess: followQueued,
  });

  /* The version and hash sent are the ones the read returned, so an unsaved edit would
     be regenerated away from. Autosave settles first, and until it does the control says
     so rather than freezing a version the user has already moved past. */
  const unsaved =
    autosave.status === "saving" ||
    autosave.status === "conflict" ||
    autosave.pending.length > 0 ||
    autosave.pendingRemovals.length > 0;
  const regenerationDisabled = unsaved || regeneration.isPending || !regenerationAvailable;

  return {
    applicationQuery,
    approvalOpen,
    autosave,
    detail,
    draft,
    draftQuery,
    editClaim,
    exactPassingRunId,
    facts,
    includeFact,
    onExactPassingRun,
    operationPanel,
    regeneration,
    regenerationAvailable,
    regenerationDisabled,
    removeClaim,
    renderRevisionId,
    selection,
    setApprovalOpen,
    setApprovedRevisionId,
    settingsPending,
    setValidationStale,
    unsaved,
    validationStale,
    watch,
    workingDraftId,
  };
};
