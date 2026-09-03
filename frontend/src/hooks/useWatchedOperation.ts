import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useCallback, useEffect, useState } from "react";

import { invalidateApplicationViews } from "../api/applications";
import type { ApplicationDetail, Operation } from "../api/contracts";
import { isTerminalOperation, operationQueryOptions } from "../api/operations";

/* Watching one Application's live work, on whichever screen queued it.

   It cannot simply be the projection's `active_operation`, because that field is only
   ever a `queued` or `running` record: the moment work finishes it becomes null. Read
   straight, a panel driven by it would vanish at the instant the Operation had something
   to say - a failure code, its guidance, the retry offer - and a failed run would leave
   no trace on the screen that started it.

   So the projection opens the watch and a query of the Operation's own closes it. The id
   is held here across that transition, and the Operation query keeps reporting the record
   after the projection has let go of it.

   `watch` is called directly by whatever queued the work, from the accepted `202`: the
   projection reports an Operation only on its next read, so waiting for it would put the
   panel on screen a poll after the press that caused it.

   Presentation remains with the owning page; this hook returns only watched data. */
export const useWatchedOperation = (
  applicationId: string,
  detail: ApplicationDetail | undefined,
): {
  /* The id under watch, which is not the same question as the record itself: the
     auto-draft chain keys its session record and its in-flight guard by the analyze
     Operation that triggered it, and needs that id before the record has arrived. */
  operationId: string | null;
  operation: Operation | undefined;
  watch: (operationId: string) => void;
} => {
  const queryClient = useQueryClient();
  const [watchedId, setWatchedId] = useState<string | null>(null);
  const activeOperationId = detail?.active_operation?.id ?? null;

  useEffect(() => {
    if (activeOperationId !== null) {
      setWatchedId(activeOperationId);
    }
  }, [activeOperationId]);

  /* Cleared when the user moves to another Application: the previous one's finished work
     is not this one's. */
  useEffect(() => setWatchedId(null), [applicationId]);

  const watchedQuery = useQuery({
    ...operationQueryOptions(watchedId ?? ""),
    enabled: watchedId !== null,
  });
  /* The Operation's own query is authoritative once it has answered: it is the only one of
     the two that reports a finished record, because `active_operation` is only ever queued
     or running and the projection lets go the moment work ends.

     The projection's copy is the fallback, and it earns its place at the other end of the
     Operation's life: it arrives with the page, so a reload mid-run paints the panel from
     the first render instead of after a second round trip. */
  const operation = watchedQuery.data?.id === watchedId ? watchedQuery.data : (detail?.active_operation ?? undefined);

  /* The projection is refreshed once the watched Operation reaches a terminal status:
     what it produced - a new analysis, a draft, the stage that follows - is the
     projection's to report, and it stopped polling when `active_operation` went null.

     The board is refreshed with it. A finished render is what moves a row to Ready and
     what the board counts under "מוכנים", so invalidating the detail alone left the
     numbers on the board reporting the state before the run - until a manual reload. */
  const terminal = operation !== undefined && isTerminalOperation(operation);
  useEffect(() => {
    if (terminal) {
      void invalidateApplicationViews(queryClient, applicationId);
    }
  }, [applicationId, queryClient, terminal, operation?.id]);

  const watch = useCallback((operationId: string) => setWatchedId(operationId), []);

  return {
    operation,
    operationId: watchedId,
    watch,
  };
};
