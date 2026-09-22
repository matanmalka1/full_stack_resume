import { useCallback, useEffect, useRef, useState } from "react";

import { ApiProblem } from "@/api/client";
import { type DraftPatch, updateWorkingDraft } from "@/api/drafts";
import type { ClaimAddition, ClaimPatch, WorkingDraftUpdate } from "@/api/contracts";

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
  pendingAdditions: ClaimAddition[];
  pendingSectionOrder: string[] | null;
  pendingClaimOrders: Record<string, string[]>;
}

interface UseDraftAutosaveOptions {
  workingDraftId: string | null;
  etag: string | null;
  onConflict: () => Promise<string | null>;
  onSaved: (update: WorkingDraftUpdate, etag: string | null) => void;
}

const emptyPatch = (patch: DraftPatch): boolean =>
  patch.claim_edits.length === 0 &&
  patch.claim_removals.length === 0 &&
  patch.claim_additions.length === 0 &&
  patch.section_order === undefined &&
  Object.keys(patch.claim_orders ?? {}).length === 0;

const storageKey = (workingDraftId: string): string => `cv-engine:autosave:${workingDraftId}`;

interface StoredBuffer {
  edits: ClaimPatch[];
  removals: string[];
  additions: ClaimAddition[];
  sectionOrder?: string[];
  claimOrders?: Record<string, string[]>;
}

/* Best-effort only: a full or disabled storage must never block typing or saving. */
const readStoredBuffer = (workingDraftId: string): StoredBuffer | null => {
  try {
    const raw = window.sessionStorage.getItem(storageKey(workingDraftId));
    return raw === null ? null : (JSON.parse(raw) as StoredBuffer);
  } catch {
    return null;
  }
};

const writeStoredBuffer = (workingDraftId: string, buffer: StoredBuffer): void => {
  try {
    if (
      buffer.edits.length === 0 &&
      buffer.removals.length === 0 &&
      buffer.additions.length === 0 &&
      buffer.sectionOrder === undefined &&
      Object.keys(buffer.claimOrders ?? {}).length === 0
    ) {
      window.sessionStorage.removeItem(storageKey(workingDraftId));
      return;
    }
    window.sessionStorage.setItem(storageKey(workingDraftId), JSON.stringify(buffer));
  } catch {
    /* ignore */
  }
};

/* A.4 autosave, and the serialisation debounce alone does not give.

   `activeSave` makes only one request outstanding at a time - a second call to `send`
   while one is in flight returns that same promise instead of starting another - and the
   request always reads `token.current` at call time rather than a value captured when the
   user typed. That alone stops an older response from installing an older ETag over a
   newer one.

   What it does not do is get anything typed *during* that request out the door: the
   debounce timer such an edit sets can fire before the request settles, find a save
   already in flight, and do nothing - and by then the timer that fired is already spent,
   so nothing is left counting down for it. `send` closes that gap itself, by recursing
   into another `send()` immediately after a success, as part of the same promise rather
   than a separately scheduled one - which is also what lets `settle()` await one call and
   know the buffer is genuinely empty, not just that the request it happened to catch in
   flight has finished.

   Everything that must not race is a ref. Component state here would be read at the value
   it had when the callback was created, which is exactly the staleness this is
   preventing. */
export const useDraftAutosave = ({ workingDraftId, etag, onConflict, onSaved }: UseDraftAutosaveOptions) => {
  const edits = useRef(new Map<string, ClaimPatch>());
  const removals = useRef(new Set<string>());
  const additions = useRef<ClaimAddition[]>([]);
  const sectionOrder = useRef<string[] | null>(null);
  const claimOrders = useRef(new Map<string, string[]>());
  const inFlight = useRef(false);
  const activeSave = useRef<Promise<void> | null>(null);
  const token = useRef(etag);
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const halted = useRef(false);
  /* `send` recurses into itself on success (below) to drain whatever was queued while it was
     in flight, and the unmount cleanup effect below needs to reach it too - both from
     closures that must not call a `send` frozen at an earlier render (a stale
     `workingDraftId` or `onSaved`), so both go through this ref instead of the function
     value directly. */
  const sendRef = useRef<() => Promise<void>>(async () => undefined);
  const [state, setState] = useState<AutosaveState>({
    status: "idle",
    message: null,
    pending: [],
    pendingRemovals: [],
    pendingAdditions: [],
    pendingSectionOrder: null,
    pendingClaimOrders: {},
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
      pendingAdditions: [...additions.current],
      pendingSectionOrder: sectionOrder.current === null ? null : [...sectionOrder.current],
      pendingClaimOrders: Object.fromEntries(claimOrders.current),
    });
  }, []);

  /* Mirrors the in-memory buffer so a refresh or crash does not lose text the "saved in
     the browser" message already promises. Writes on every mutation and is cleared the
     moment a save actually lands, so it never outlives what it stands in for. */
  const mirror = useCallback(() => {
    if (workingDraftId === null) {
      return;
    }
    writeStoredBuffer(workingDraftId, {
      edits: [...edits.current.values()],
      removals: [...removals.current],
      additions: [...additions.current],
      sectionOrder: sectionOrder.current ?? undefined,
      claimOrders: Object.fromEntries(claimOrders.current),
    });
  }, [workingDraftId]);

  /* Warns before the tab or navigation discards text the buffer has not yet sent. */
  useEffect(() => {
    const handler = (event: BeforeUnloadEvent) => {
      if (
        edits.current.size === 0 &&
        removals.current.size === 0 &&
        additions.current.length === 0 &&
        sectionOrder.current === null &&
        claimOrders.current.size === 0
      ) {
        return;
      }
      event.preventDefault();
    };
    window.addEventListener("beforeunload", handler);
    return () => window.removeEventListener("beforeunload", handler);
  }, []);

  /* Put a rejected patch back so nothing the user wrote is lost - but never over a newer
     edit to the same claim. The buffer is the latest intent, and a restore is older. */
  const restore = useCallback(
    (patch: DraftPatch) => {
      for (const edit of patch.claim_edits) {
        if (!edits.current.has(edit.claim_id)) {
          edits.current.set(edit.claim_id, edit);
        }
      }
      for (const claimId of patch.claim_removals) {
        removals.current.add(claimId);
      }
      additions.current = [...patch.claim_additions, ...additions.current];
      if (sectionOrder.current === null && patch.section_order !== undefined) {
        sectionOrder.current = [...patch.section_order];
      }
      for (const [section, order] of Object.entries(patch.claim_orders ?? {})) {
        if (!claimOrders.current.has(section)) claimOrders.current.set(section, [...order]);
      }
      mirror();
    },
    [mirror],
  );

  const send = useCallback((): Promise<void> => {
    if (activeSave.current !== null) return activeSave.current;
    if (halted.current || workingDraftId === null) return Promise.resolve();

    const task = (async () => {
      const patch: DraftPatch = {
        claim_edits: [...edits.current.values()],
        claim_removals: [...removals.current],
        claim_additions: [...additions.current],
        ...(sectionOrder.current === null ? {} : { section_order: [...sectionOrder.current] }),
        ...(claimOrders.current.size === 0 ? {} : { claim_orders: Object.fromEntries(claimOrders.current) }),
      };

      if (emptyPatch(patch) || token.current === null) {
        return;
      }

      edits.current.clear();
      removals.current.clear();
      additions.current = [];
      sectionOrder.current = null;
      claimOrders.current.clear();
      inFlight.current = true;
      publish("saving");

      try {
        const result = await updateWorkingDraft(workingDraftId, token.current, patch);
        token.current = result.etag;
        onSaved(result.update, result.etag);
        publish("saved");
        mirror();
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
          error instanceof ApiProblem ? error.problem.detail : "השמירה נכשלה. הטקסט נשמר בדפדפן ואפשר לנסות שוב.",
        );
        return;
      } finally {
        inFlight.current = false;
        activeSave.current = null;
      }

      /* Whatever arrived while that request was open goes now, against the token it just
       returned - as part of this same promise, not fired separately. `settle()` awaits
       exactly this promise to know the buffer is genuinely empty before it lets the caller
       navigate away; a follow-up send kicked off from an effect would resolve on its own
       schedule, outside `settle()`'s wait. */
      await sendRef.current();
    })();
    activeSave.current = task;
    void task.then(() => {
      if (activeSave.current === task) activeSave.current = null;
      return undefined;
    });
    return task;
  }, [mirror, onConflict, onSaved, publish, restore, workingDraftId]);

  useEffect(() => {
    sendRef.current = send;
  }, [send]);

  const schedule = useCallback(() => {
    if (timer.current !== null) {
      clearTimeout(timer.current);
    }
    timer.current = setTimeout(() => {
      timer.current = null;
      void send();
    }, AUTOSAVE_DEBOUNCE_MS);
  }, [send]);

  /* Recovers a buffer left behind by a reload or crash before the draft's own state
     finished loading. Runs once per draft id; the save it schedules is a normal save,
     and success clears the entry like any other. */
  useEffect(() => {
    if (workingDraftId === null) {
      return;
    }
    const stored = readStoredBuffer(workingDraftId);
    if (stored === null) {
      return;
    }
    for (const edit of stored.edits) {
      edits.current.set(edit.claim_id, edit);
    }
    for (const claimId of stored.removals) {
      removals.current.add(claimId);
    }
    additions.current = [...additions.current, ...stored.additions];
    sectionOrder.current = stored.sectionOrder ?? null;
    claimOrders.current = new Map(Object.entries(stored.claimOrders ?? {}));
    publish("idle");
    schedule();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [workingDraftId]);

  const queueEdit = useCallback(
    (patch: ClaimPatch) => {
      edits.current.set(patch.claim_id, patch);
      removals.current.delete(patch.claim_id);
      mirror();
      publish(halted.current ? "conflict" : "idle");
      schedule();
    },
    [mirror, publish, schedule],
  );

  const queueRemoval = useCallback(
    (claimId: string) => {
      edits.current.delete(claimId);
      removals.current.add(claimId);
      for (const [section, order] of claimOrders.current) {
        if (order.includes(claimId))
          claimOrders.current.set(
            section,
            order.filter((id) => id !== claimId),
          );
      }
      mirror();
      publish(halted.current ? "conflict" : "idle");
      schedule();
    },
    [mirror, publish, schedule],
  );

  const queueAddition = useCallback(
    (addition: ClaimAddition) => {
      additions.current = [...additions.current, addition];
      mirror();
      publish(halted.current ? "conflict" : "idle");
      schedule();
    },
    [mirror, publish, schedule],
  );

  const queueSectionOrder = useCallback(
    (order: string[]) => {
      sectionOrder.current = [...order];
      mirror();
      publish(halted.current ? "conflict" : "idle");
      schedule();
    },
    [mirror, publish, schedule],
  );

  const queueClaimOrder = useCallback(
    (section: string, order: string[]) => {
      claimOrders.current.set(section, [...order]);
      mirror();
      publish(halted.current ? "conflict" : "idle");
      schedule();
    },
    [mirror, publish, schedule],
  );

  /* Blur: the debounce is a convenience for typing, not a reason to hold a finished edit. */
  const flush = useCallback(() => {
    if (timer.current !== null) {
      clearTimeout(timer.current);
      timer.current = null;
    }
    void send();
  }, [send]);

  /* Wait for the serial queue before changing context. Refusals retain local text. */
  const settle = useCallback(async (): Promise<boolean> => {
    if (timer.current !== null) {
      clearTimeout(timer.current);
      timer.current = null;
    }
    await send();
    return (
      !halted.current &&
      !inFlight.current &&
      edits.current.size === 0 &&
      removals.current.size === 0 &&
      additions.current.length === 0 &&
      sectionOrder.current === null &&
      claimOrders.current.size === 0
    );
  }, [send]);

  /* The user chose the server's version. Their text is discarded because they said so -
     which is the only way it is ever discarded. */
  const discardLocal = useCallback(() => {
    edits.current.clear();
    removals.current.clear();
    additions.current = [];
    sectionOrder.current = null;
    claimOrders.current.clear();
    halted.current = false;
    mirror();
    publish("idle");
  }, [mirror, publish]);

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
        timer.current = null;
      }
      void sendRef.current();
    },
    [],
  );

  return {
    ...state,
    discardLocal,
    flush,
    queueAddition,
    queueClaimOrder,
    queueEdit,
    queueRemoval,
    queueSectionOrder,
    reapplyLocal,
    settle,
  };
};
