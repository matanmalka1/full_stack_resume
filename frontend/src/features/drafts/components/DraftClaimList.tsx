import { type ReactNode, useCallback, useEffect, useRef, useState } from "react";

import type { DraftClaim, WorkingDraft, WorkingDraftFacts } from "@/api/contracts";
import { Button } from "@/ui/Button";
import { Callout } from "@/ui/Callout";
import type { DraftClaimActions } from "../model/drafts.types";
import { linkedFacts, removability } from "../model/draftClaims";
import { DraftClaimRow } from "./DraftClaimRow";

/* The window a confirmed removal sits in before it actually reaches the server - long
   enough to read and tap "ביטול", short enough that the row leaving the list still reads
   as a consequence of the click that confirmed it. */
const REMOVAL_UNDO_MS = 6000;

interface DraftClaimListProps {
  actions: DraftClaimActions;
  claims: DraftClaim[];
  draft: WorkingDraft;
  /* Built only for a `pending` line, which is the only line that can be resolved into a
     fact. Passed as a function so the sections that have that context supply it and the
     identity card, which has no section to attach a fact to, simply does not. */
  factResolution?: (claim: DraftClaim) => ReactNode;
  facts: WorkingDraftFacts | undefined;
  /* Rendered instead of the list when the outline names no claims here. */
  emptyLabel: string;
}

/* One run of claims as a list of rows.

   It is where the per-claim answers are worked out - which facts back a line, and which
   command would remove it - so both are decided by one policy in one place rather than by
   each row for itself. The rows below it draw what they are given. */
export const DraftClaimList = ({
  actions,
  claims,
  draft,
  emptyLabel,
  factResolution,
  facts,
}: DraftClaimListProps): ReactNode => {
  const [pendingRemoval, setPendingRemoval] = useState<DraftClaim | null>(null);
  const timeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  /* Read by the unmount effect below, which cannot take `pendingRemoval` or `actions` as
     dependencies without re-running - and committing - on every render that changes
     either. */
  const pendingRemovalRef = useRef<DraftClaim | null>(null);
  const actionsRef = useRef(actions);
  useEffect(() => {
    pendingRemovalRef.current = pendingRemoval;
    actionsRef.current = actions;
  }, [actions, pendingRemoval]);

  const clearTimer = useCallback(() => {
    if (timeoutRef.current !== null) {
      clearTimeout(timeoutRef.current);
      timeoutRef.current = null;
    }
  }, []);

  /* Confirming removal never fires the real command straight away: it stages the claim,
     hides its row, and only sends `onRemove` once the undo window lapses untouched. A
     second removal confirmed while one is still staged commits the first immediately
     rather than losing track of it. */
  const requestRemoval = useCallback(
    (claim: DraftClaim) => {
      const previous = pendingRemovalRef.current;
      clearTimer();
      if (previous !== null) {
        actionsRef.current.onRemove(previous);
      }
      setPendingRemoval(claim);
      timeoutRef.current = setTimeout(() => {
        timeoutRef.current = null;
        setPendingRemoval(null);
        actionsRef.current.onRemove(claim);
      }, REMOVAL_UNDO_MS);
    },
    [clearTimer],
  );

  const cancelRemoval = useCallback(() => {
    clearTimer();
    setPendingRemoval(null);
  }, [clearTimer]);

  /* Leaving the screen with a removal still staged must not silently drop it - it
     commits on unmount instead of vanishing along with the timer. */
  useEffect(
    () => () => {
      clearTimer();
      if (pendingRemovalRef.current !== null) {
        actionsRef.current.onRemove(pendingRemovalRef.current);
      }
    },
    [clearTimer],
  );

  const visibleClaims = claims.filter((claim) => claim.claim_id !== pendingRemoval?.claim_id);
  const rowActions: DraftClaimActions = { ...actions, onRemove: requestRemoval };

  return (
    <div className="flex flex-col gap-3">
      {visibleClaims.length === 0 ? (
        <p className="text-support leading-6 text-cv-text-muted">{emptyLabel}</p>
      ) : (
        <ul className="flex flex-col divide-y divide-cv-border">
          {visibleClaims.map((claim) => (
            <DraftClaimRow
              actions={rowActions}
              claim={claim}
              facts={linkedFacts(claim, facts)}
              factResolution={claim.claim_type === "pending" ? factResolution?.(claim) : undefined}
              key={claim.claim_id}
              removal={removability(claim, draft, facts)}
            />
          ))}
        </ul>
      )}

      {pendingRemoval === null ? null : (
        <Callout
          action={
            <Button onClick={cancelRemoval} size="compact" variant="secondary">
              ביטול ההסרה
            </Button>
          }
          role="alert"
          title="השורה הוסרה"
          tone="warning"
        >
          <p dir="auto">אפשר להחזיר אותה כל עוד ההודעה הזו מוצגת.</p>
        </Callout>
      )}
    </div>
  );
};
