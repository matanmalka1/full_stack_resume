import { useMutation, useQueryClient } from "@tanstack/react-query";

import type { Operation } from "@/api/contracts";
import { cancelOperation, operationQueryKey, retryOperation } from "@/api/operations";

/* The record's own two commands: cancel a live run, retry one that ended. Each answer is
   written to the record's cache entry, and a retry's new run is handed to the host's watch
   so the screen keeps reporting in place.

   One retry key per original Operation: an uncertain response can be retried safely,
   while the new record rotates the key for its own future retry. Derived rather than
   cached, since a discarded memo would mint a new key on the same Operation and send a
   second one to the server. */
export const useOperationCommands = (operation: Operation, onQueued: (operationId: string) => void) => {
  const queryClient = useQueryClient();
  const retryKey = `retry:${operation.id}`;

  const cancel = useMutation({
    mutationFn: () => cancelOperation(operation.id),
    onSuccess: (cancelled) => {
      queryClient.setQueryData(operationQueryKey(cancelled.id), cancelled);
    },
  });
  const retry = useMutation({
    mutationFn: () => retryOperation(operation.id, retryKey),
    onSuccess: ({ operation: queued }) => {
      queryClient.setQueryData(operationQueryKey(queued.id), queued);
      onQueued(queued.id);
    },
  });

  return { cancel, retry, error: cancel.error ?? retry.error };
};
