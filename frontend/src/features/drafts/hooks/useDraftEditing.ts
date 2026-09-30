import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useCallback } from "react";

import { applicationDetailQueryKey } from "@/api/applications";
import type { DraftClaim } from "@/api/contracts";
import {
  documentQueryKey,
  documentQueryOptions,
  regenerateClaim,
  regenerateSection,
  selectionOverlay,
  updateSelection,
} from "@/api/documents";
import { type QueuedOperation, operationQueryKey } from "@/api/operations";
import { aiAvailability } from "@/api/settings";
import { useSettings } from "@/api/useSettings";
import type { DraftClaimActions, EditableDocument } from "../model/drafts.types";
import { removability } from "../model/draftClaims";
import { type AutosaveState, useDraftAutosave } from "./useDraftAutosave";
import { useDraftHistory } from "./useDraftHistory";

interface UseDraftEditingOptions {
  applicationId: string;
  /* The document with content; undefined while there is none to edit. Its `facts` are the
     accounting the removal and include decisions read. */
  draft: EditableDocument | undefined;
  etag: string | null;
  /* Regeneration is a durable Operation. The accepted `202` goes to the screen's own
     watch rather than to a route of its own. */
  onOperationQueued: (operationId: string) => void;
  /* This Application's work is under way (`isOperationLive`). See `DraftClaimActions.locked`. */
  operationLive: boolean;
}

export interface DraftEditing {
  /* AI regeneration is configured off or has no provider. Distinct from "still asking
     Settings", so the screen never claims unavailability it has not established. */
  aiUnavailable: boolean;
  claimActions: DraftClaimActions;
  /* A 409 stopped the queue. The dialog owns what happens next; nothing merges and
     nothing is dropped. */
  conflict: {
    discardLocal: () => void;
    open: boolean;
    pending: AutosaveState["pending"];
    pendingAdditions: AutosaveState["pendingAdditions"];
    pendingRemovals: AutosaveState["pendingRemovals"];
    pendingClaimOrders: AutosaveState["pendingClaimOrders"];
    reapplyLocal: () => void;
  };
  /* Anything the server has not accepted yet: a buffered edit, a save in flight, or a
     halted queue. */
  dirty: boolean;
  flush: () => void;
  settle: () => Promise<boolean>;
  regenerateSection: (section: string) => void;
  regenerationError: unknown;
  saveState: AutosaveState;
  selectionError: unknown;
  selectionPending: boolean;
  history: {
    canRedo: boolean;
    canUndo: boolean;
    moveClaim: (section: string, index: number, offset: -1 | 1) => void;
    redo: () => void;
    undo: () => void;
  };
  visibleDraft: EditableDocument | undefined;
}

/* Every write this screen makes to the draft: the autosave buffer, the two removal
   routes, the fact include, and regeneration. Reading is `useDraftDocument`'s; approval
   and validation are their own.

   Nothing here decides workflow. Each command is the backend's, addressed to the exact
   version the read returned, and a refusal is reported rather than worked around. */
export const useDraftEditing = ({
  applicationId,
  draft,
  etag,
  onOperationQueued,
  operationLive,
}: UseDraftEditingOptions): DraftEditing => {
  const queryClient = useQueryClient();
  const { isPending: settingsPending, settings } = useSettings();
  const regenerationAvailable = aiAvailability(settings) === "available";

  /* The document is keyed by its Application; with no content there is nothing to save. */
  const editingKey = draft === undefined ? null : applicationId;

  /* A save changes the document, so the read that produced it is stale by definition. Keep
     its body and token together until the invalidated read replaces both: installing the
     response token beside the previous outline would briefly construct a read that never
     existed. The autosave queue owns the returned token needed by its next write. */
  const onSaved = useCallback(() => {
    void queryClient.invalidateQueries({ queryKey: documentQueryKey(applicationId) });
    void queryClient.invalidateQueries({ queryKey: applicationDetailQueryKey(applicationId) });
  }, [applicationId, queryClient]);

  /* A 409 says the read behind both the editor and its ETag is obsolete. Refresh them as
     one read so the conflict comparison and the next If-Match name the same document.
     `fetchQuery` is deliberate here: invalidation alone would not wait for or return the
     replacement token. */
  const onConflict = useCallback(async () => {
    const current = await queryClient.fetchQuery(documentQueryOptions(applicationId));
    return current.etag;
  }, [applicationId, queryClient]);

  const autosave = useDraftAutosave({ applicationId: editingKey, etag, onConflict, onSaved });
  const history = useDraftHistory({
    draft,
    queueClaimOrder: autosave.queueClaimOrder,
    queueEdit: (claim, text) => autosave.queueEdit({ claim_id: claim.claim_id, fact_ids: claim.fact_ids, text }),
  });

  /* §14 `update_selection`: the overlay is absolute, so every change starts from what the
     document's selection currently holds and adds one decision to it. Sending only what
     moved would drop every pin and exclusion the user made before. The hash sent is the
     one read back after the buffer settled, so the change is addressed to the document the
     user's last edit produced. */
  const selection = useMutation({
    mutationFn: async (change: { pinned?: string[]; excluded?: string[] }) => {
      if (draft === undefined) {
        throw new Error("a selection change was offered before the document arrived");
      }
      if (!(await autosave.settle())) {
        throw new Error("Selection cannot change until local draft edits are saved");
      }
      const current = await queryClient.fetchQuery({ ...documentQueryOptions(applicationId), staleTime: 0 });
      const overlay = selectionOverlay(current.document);
      return updateSelection(applicationId, current.document.document_hash, {
        pinned_fact_ids: [...new Set([...overlay.pinned_fact_ids, ...(change.pinned ?? [])])],
        excluded_fact_ids: [...new Set([...overlay.excluded_fact_ids, ...(change.excluded ?? [])])],
      });
    },
    onSuccess: () => {
      /* Selection and content changed together, and the hash with them. Nothing from the
         response is seeded: the refreshed reads report the document that now exists. */
      onSaved();
    },
  });

  const regeneration = useMutation({
    mutationFn: async (target: { claimId?: string; keepText?: boolean; section?: string }) => {
      if (draft === undefined) {
        throw new Error("a regeneration was offered before the draft arrived");
      }
      /* One key per target and document: a resent regeneration of the same line of the
         same document is the same command, and a changed document is a different one. */
      const key = `${draft.document_hash}:${target.claimId ?? target.section ?? ""}${target.keepText === true ? ":review" : ""}`;

      return target.claimId === undefined
        ? regenerateSection(draft, target.section ?? "", key)
        : regenerateClaim(draft, target.claimId, key, target.keepText === true);
    },
    /* §14 regeneration is an Operation, reported beside the draft it is rewriting rather
       than followed to a screen of its own. The accepted `202` seeds the Operation's own
       query so the overlay appears with the press rather than a poll later. */
    onSuccess: ({ operation }: QueuedOperation) => {
      queryClient.setQueryData(operationQueryKey(operation.id), operation);
      onOperationQueued(operation.id);
    },
  });

  /* The hash sent is the one the read returned, so an unsaved edit would be regenerated
     away from. Autosave settles first, and until it does the control says
     so rather than freezing a version the user has already moved past. */
  const dirty =
    autosave.status === "saving" ||
    autosave.status === "conflict" ||
    autosave.pending.length > 0 ||
    autosave.pendingRemovals.length > 0 ||
    autosave.pendingAdditions.length > 0 ||
    Object.keys(autosave.pendingClaimOrders).length > 0;

  /* Which command removes a line is `removability`'s answer, not a guess made here: the
     patch takes the unauthorized claims, and a fact-authorized one is removed by
     excluding the facts behind it. */
  const removeClaim = (claim: DraftClaim) => {
    if (draft === undefined) {
      return;
    }
    const { route } = removability(claim, draft, draft);

    if (route === "patch") {
      autosave.queueRemoval(claim.claim_id);
    }
    if (route === "selection") {
      selection.mutate({ excluded: claim.fact_ids });
    }
  };

  return {
    aiUnavailable: !settingsPending && !regenerationAvailable,
    claimActions: {
      /* The fact links are the claim's own. An edit changes wording, not what backs it -
         relinking is a separate decision, and sending a different set here would silently
         re-authorize a line the user only rephrased. */
      onEdit: history.edit,
      onCommit: autosave.flush,
      onAdd: (section, text) => autosave.queueAddition({ section, text }),
      onRegenerate: (claim) => regeneration.mutate({ claimId: claim.claim_id }),
      onReview: (claim) => regeneration.mutate({ claimId: claim.claim_id, keepText: true }),
      onRemove: removeClaim,
      regenerationDisabled: operationLive || dirty || regeneration.isPending || !regenerationAvailable,
      locked: operationLive,
    },
    conflict: {
      discardLocal: () => {
        autosave.discardLocal();
        history.reset();
      },
      open: autosave.status === "conflict",
      pending: autosave.pending,
      pendingAdditions: autosave.pendingAdditions,
      pendingRemovals: autosave.pendingRemovals,
      pendingClaimOrders: autosave.pendingClaimOrders,
      reapplyLocal: autosave.reapplyLocal,
    },
    dirty,
    flush: autosave.flush,
    settle: autosave.settle,
    history: {
      canRedo: history.canRedo,
      canUndo: history.canUndo,
      moveClaim: history.moveClaim,
      redo: history.redo,
      undo: history.undo,
    },
    regenerateSection: (section) => regeneration.mutate({ section }),
    regenerationError: regeneration.error,
    saveState: autosave,
    selectionError: selection.error,
    selectionPending: selection.isPending,
    visibleDraft: history.visibleDraft,
  };
};
