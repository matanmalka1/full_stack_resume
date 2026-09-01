import { useCallback, useEffect, useRef, useState } from "react";

import { ApiProblem } from "../../api/client";
import { type DraftPatch, updateWorkingDraft } from "../../api/drafts";
import type { ClaimPatch, WorkingDraftUpdate } from "../../api/contracts";

const AUTOSAVE_DEBOUNCE_MS = 700;

export type AutosaveStatus = "idle" | "saving" | "saved" | "failed" | "conflict";

export interface AutosaveState {
  status: AutosaveStatus;
  /* The safe message behind a `failed`, ready to be shown as-is. */
  message: string | null;
  /* What the user has written that the server has not accepted yet. It survives a
     failure and a conflict: A.4 requires the local text to be preserved and offered as an
     explicit choice, never dropped. */
  pending: ClaimPatch[];
  pendingRemovals: string[];
}

interface UseDraftAutosaveOptions {
  workingDraftId: string | null;
  etag: string | null;
  onConflict: () => Promise<string | null>;
  onSaved: (update: WorkingDraftUpdate, etag: string | null) => void;
}

const emptyPatch = (patch: DraftPatch): boolean =>
  patch.claim_edits.length === 0 && patch.claim_removals.length === 0;

/* A.4 autosave, and the serialisation debounce alone does not give.

   Two saves in flight let an older response install an older ETag over a newer one, and
   the next save then conflicts against a token the server has already moved past. So:
   one request at a time, edits coalesced by claim while one is running, and the token for
   the next request taken from the response that just settled rather than from whatever was
   captured when the user typed.

   Everything that must not race is a ref. Component state here would be read at the value
   it had when the callback was created, which is exactly the stale token this is
   preventing. */
export const useDraftAutosave = ({
  workingDraftId,
  etag,
  onConflict,
  onSaved,
}: UseDraftAutosaveOptions) => {
  const edits = useRef(new Map<string, ClaimPatch>());
  const removals = useRef(new Set<string>());
  const inFlight = useRef(false);
  const token = useRef(etag);
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const halted = useRef(false);
  const [state, setState] = useState<AutosaveState>({
    status: "idle",
    message: null,
    pending: [],
    pendingRemovals: [],
  });

  useEffect(() => {
    /* A fresh read replaces the token. It is never narrowed to null by an in-flight
       save's response, which is why the response assigns it directly instead. */
    if (etag !== null) {
      token.current = etag;
    }
  }, [etag]);

  const publish = useCallback((status: AutosaveStatus, message: string | null = null) => {
    setState({
      status,
      message,
      pending: [...edits.current.values()],
      pendingRemovals: [...removals.current],
    });
  }, []);

  /* Put a rejected patch back so nothing the user wrote is lost - but never over a newer
     edit to the same claim. The buffer is the latest intent, and a restore is older. */
  const restore = useCallback((patch: DraftPatch) => {
    for (const edit of patch.claim_edits) {
      if (!edits.current.has(edit.claim_id)) {
        edits.current.set(edit.claim_id, edit);
      }
    }
    for (const claimId of patch.claim_removals) {
      removals.current.add(claimId);
    }
  }, []);

  const send = useCallback(async (): Promise<void> => {
    if (inFlight.current || halted.current || workingDraftId === null) {
      return;
    }

    const patch: DraftPatch = {
      claim_edits: [...edits.current.values()],
      claim_removals: [...removals.current],
    };

    if (emptyPatch(patch) || token.current === null) {
      return;
    }

    edits.current.clear();
    removals.current.clear();
    inFlight.current = true;
    publish("saving");

    try {
      const result = await updateWorkingDraft(workingDraftId, token.current, patch);
      token.current = result.etag;
      onSaved(result.update, result.etag);
      publish("saved");
    } catch (error) {
      restore(patch);

      if (error instanceof ApiProblem && error.problem.status === 409) {
        /* The queue stops here. Nothing is resent automatically and nothing is merged:
           the dialog owns what happens next, and the user's text is still in the
           buffer. Its comparison and the token must come from the same fresh read. */
        halted.current = true;
        try {
          const currentToken = await onConflict();
          if (currentToken !== null) {
            token.current = currentToken;
          }
        } catch {
          /* The conflict remains an explicit choice even if its refresh failed. Reapply
             performs another fresh read, so it can recover without losing local text. */
        }
        publish("conflict", error.problem.detail);
        return;
      }

      publish(
        "failed",
        error instanceof ApiProblem
          ? error.problem.detail
          : "השמירה נכשלה. הטקסט נשמר בדפדפן ואפשר לנסות שוב.",
      );
      return;
    } finally {
      inFlight.current = false;
    }

    /* Whatever arrived while that request was open goes now, against the token it just
       returned. */
    void send();
  }, [onConflict, onSaved, publish, restore, workingDraftId]);

  const schedule = useCallback(() => {
    if (timer.current !== null) {
      clearTimeout(timer.current);
    }
    timer.current = setTimeout(() => {
      timer.current = null;
      void send();
    }, AUTOSAVE_DEBOUNCE_MS);
  }, [send]);

  const queueEdit = useCallback(
    (patch: ClaimPatch) => {
      edits.current.set(patch.claim_id, patch);
      removals.current.delete(patch.claim_id);
      publish(halted.current ? "conflict" : "idle");
      schedule();
    },
    [publish, schedule],
  );

  const queueRemoval = useCallback(
    (claimId: string) => {
      edits.current.delete(claimId);
      removals.current.add(claimId);
      publish(halted.current ? "conflict" : "idle");
      schedule();
    },
    [publish, schedule],
  );

  /* Blur: the debounce is a convenience for typing, not a reason to hold a finished edit. */
  const flush = useCallback(() => {
    if (timer.current !== null) {
      clearTimeout(timer.current);
      timer.current = null;
    }
    void send();
  }, [send]);

  /* The user chose the server's version. Their text is discarded because they said so -
     which is the only way it is ever discarded. */
  const discardLocal = useCallback(() => {
    edits.current.clear();
    removals.current.clear();
    halted.current = false;
    publish("idle");
  }, [publish]);

  /* The user chose to apply their text over the current version. The token now in hand
     came from a fresh read, so this is a new save against what the server actually holds,
     not a retry of the one that lost. */
  const reapplyLocal = useCallback(() => {
    void (async () => {
      try {
        /* The other tab may have saved again while the dialog was open. Read once more
           at the decision boundary and bind the user's patch to that exact version. */
        const currentToken = await onConflict();
        if (currentToken === null) {
          publish("conflict", "לא ניתן לקרוא את הגרסה הנוכחית. אפשר לנסות שוב.");
          return;
        }
        token.current = currentToken;
      } catch {
        publish("conflict", "לא ניתן לקרוא את הגרסה הנוכחית. אפשר לנסות שוב.");
        return;
      }

      halted.current = false;
      publish("idle");
      void send();
    })();
  }, [onConflict, publish, send]);

  useEffect(
    () => () => {
      if (timer.current !== null) {
        clearTimeout(timer.current);
      }
    },
    [],
  );

  return {
    ...state,
    discardLocal,
    flush,
    queueEdit,
    queueRemoval,
    reapplyLocal,
  };
};
