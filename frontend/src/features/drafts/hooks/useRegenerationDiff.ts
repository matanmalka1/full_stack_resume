import { useState } from "react";

import type { Operation } from "@/api/contracts";
import type { EditableDocument } from "../model/drafts.types";
import {
  type RegenerationChange,
  type RegenerationSnapshot,
  type RegenerationTarget,
  regenerationChanges,
  takeSnapshot,
} from "../model/regenerationDiff";

const REGENERATIONS = new Set(["regenerate_section", "regenerate_claim"]);

interface PendingSnapshot extends RegenerationSnapshot {
  /* Set once the server accepted the command; until then the snapshot belongs to no run. */
  operationId: string | null;
}

export interface RegenerationDiff {
  /* Taken at the press, before the command leaves: the lines as they read then. */
  capture: (target: RegenerationTarget) => void;
  /* The run the captured press queued. */
  bind: (operationId: string) => void;
  changes: RegenerationChange[];
  target: RegenerationTarget | null;
  dismiss: () => void;
}

/* The before/after of the last regeneration this screen queued.

   The lines are captured client-side when the regeneration is pressed, bound to the
   Operation the server accepted, and compared once that Operation has succeeded and the
   document read back carries a different hash - so the "after" is what the run wrote, not
   what the reader typed later. A failed or cancelled run changed nothing and leaves no
   diff; a later regeneration replaces it. */
export const useRegenerationDiff = ({
  draft,
  operation,
}: {
  draft: EditableDocument | undefined;
  operation: Operation | undefined;
}): RegenerationDiff => {
  const [snapshot, setSnapshot] = useState<PendingSnapshot | null>(null);
  const [result, setResult] = useState<{ target: RegenerationTarget; changes: RegenerationChange[] } | null>(null);

  const ours =
    snapshot !== null &&
    snapshot.operationId !== null &&
    operation !== undefined &&
    operation.id === snapshot.operationId &&
    REGENERATIONS.has(operation.operation_type);

  /* Settled during render, the way the history hook adopts a new read: the comparison is
     derived from the read and the run, and storing it is what freezes the "after". */
  if (ours && operation.is_terminal) {
    if (operation.status !== "succeeded") {
      setSnapshot(null);
    } else if (draft !== undefined && draft.document_hash !== snapshot.documentHash) {
      setResult({ target: snapshot.target, changes: regenerationChanges(snapshot, draft.outline) });
      setSnapshot(null);
    }
  }

  return {
    capture: (target) => {
      if (draft === undefined) return;
      setResult(null);
      setSnapshot({ ...takeSnapshot(draft.outline, draft.document_hash, target), operationId: null });
    },
    bind: (operationId) =>
      setSnapshot((current) =>
        current === null || current.operationId !== null ? current : { ...current, operationId },
      ),
    changes: result?.changes ?? [],
    target: result?.target ?? null,
    dismiss: () => setResult(null),
  };
};
