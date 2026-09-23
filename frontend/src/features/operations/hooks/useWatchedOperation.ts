import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useCallback, useEffect, useState } from "react";

import { invalidateApplicationViews } from "@/api/applications";
import type { ApplicationDetail, Operation } from "@/api/contracts";
import { isTerminalOperation, operationQueryOptions } from "@/api/operations";

/* Watching one Application's live work, on whichever screen queued it.

   It cannot simply be the projection's `active_operation`, because that field is only
   ever a `queued` or `running` record: the moment work finishes it becomes null. Read
   straight, a panel driven by it would vanish at the instant the Operation had something
   to say - a failure code, its guidance, the retry offer - and a failed run would leave
   no trace on the screen that started it.

   The latest lifecycle record also opens the watch on a direct link or reload.
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
  /* A watch whose record has not arrived yet: `watch()` from an accepted `202` or a retry
     names an id before the Operation query answers for it, and until it does the record
     on hand (if any) is the previous run's. The work is live in that window even though
     nothing on screen can report its status yet. */
  awaitingRecord: boolean;
  /* The watched run is terminal and the views it changed have been read again. What a run
     produced is the projection's to report, so the moment a success is "done" for the
     reader is when that read has landed, not when the Operation record turned terminal. */
  settled: boolean;
  watch: (operationId: string) => void;
} => {
  const queryClient = useQueryClient();
  const [watched, setWatched] = useState<{ applicationId: string; id: string } | null>(null);
  const projectedOperation = detail?.active_operation ?? detail?.latest_operation ?? undefined;
  const projectedId = projectedOperation?.id ?? null;
  /* Scope the local watch during render, before effects run. A late response or a cached
     result from the previous URL must never become this Application's continuation. */
  const watchedId = watched?.applicationId === applicationId ? watched.id : projectedId;

  useEffect(() => {
    if (projectedId !== null) {
      // Retain the server's latest lifecycle record, including terminal outcomes on reload.
      // oxlint-disable-next-line react/set-state-in-effect
      setWatched({ applicationId, id: projectedId });
    }
  }, [applicationId, projectedId]);

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
  const candidate = watchedQuery.data?.id === watchedId ? watchedQuery.data : projectedOperation;
  const operation = candidate?.application_id === applicationId ? candidate : undefined;

  /* The projection is refreshed once the watched Operation reaches a terminal status:
     what it produced - a new analysis, a draft, the stage that follows - is the
     projection's to report, and it stopped polling when `active_operation` went null.

     The board is refreshed with it. A finished render is what moves a row to Ready and
     what the board counts under "מוכנים", so invalidating the detail alone left the
     numbers on the board reporting the state before the run - until a manual reload. */
  /* Keyed by the run, not by a boolean: two terminal records replacing each other without
     a live one between them - a retry that finished before a poll saw it running - left a
     boolean dependency at `true` and never refreshed for the second. The completion is
     recorded under the same key, and a cleaned-up effect never records, so a late refresh
     for an earlier run or another Application cannot mark this one as settled. `finally`,
     because a refetch that failed has still finished: the reader is not held on a run
     whose refresh will never succeed. */
  const terminalKey =
    operation !== undefined && isTerminalOperation(operation) ? `${applicationId}:${operation.id}` : null;
  const [settledKey, setSettledKey] = useState<string | null>(null);
  useEffect(() => {
    if (terminalKey === null) return;
    let current = true;
    void invalidateApplicationViews(queryClient, applicationId).finally(() => {
      if (current) setSettledKey(terminalKey);
    });
    return () => {
      current = false;
    };
  }, [applicationId, queryClient, terminalKey]);

  const watch = useCallback((operationId: string) => setWatched({ applicationId, id: operationId }), [applicationId]);

  return {
    /* A read that failed is not a record on its way: the screen stops holding for it. */
    awaitingRecord: watchedId !== null && operation?.id !== watchedId && !watchedQuery.isError,
    operation,
    operationId: operation?.id ?? watchedId,
    settled: terminalKey !== null && settledKey === terminalKey,
    watch,
  };
};
