import { useEffect, useState } from "react";

import type { Operation } from "@/api/contracts";

const CANCEL_REVEAL_DELAY_MS = 4_000;

/* Cancel is offered only once a live run has taken a while, for the reason the report
   gives: a short run must not flash a destructive control nobody could use in time. The
   phone's run bar keeps the same delay, so the two places that offer cancel agree. */
export const useCancelReveal = (operation: Operation | undefined): boolean => {
  const [revealedId, setRevealedId] = useState<string | null>(null);
  const id = operation?.id;
  const terminal = operation?.is_terminal ?? true;

  useEffect(() => {
    if (id === undefined || terminal) return undefined;
    const timeout = window.setTimeout(() => setRevealedId(id), CANCEL_REVEAL_DELAY_MS);
    return () => window.clearTimeout(timeout);
  }, [id, terminal]);

  return id !== undefined && revealedId === id;
};
