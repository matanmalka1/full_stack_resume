import type { Operation } from "@/api/contracts";
import { phaseLabels, statusLabels } from "./operationLabels";

/* An Operation has two machine axes, but the reader needs one answer to "what is
   happening now?". Prefer a meaningful live phase, while collapsing the generic
   queued/executing phases into the status vocabulary they merely repeat. Terminal
   status always wins: a stale last phase must not describe completed work as active. */
export const operationProgressLabel = (operation: Operation): string => {
  if (operation.is_terminal) return statusLabels[operation.status];

  if (operation.phase === "queued" || operation.phase === "executing") {
    return statusLabels[operation.status];
  }

  return phaseLabels[operation.phase];
};
