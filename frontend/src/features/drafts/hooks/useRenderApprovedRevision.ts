import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useRef } from "react";

import { operationQueryKey } from "@/api/operations";
import { approvedRevisionQueryOptions, renderApprovedRevision } from "@/api/revisions";

/* The render step's command, held by the editor rather than by the panel that offers it.

   The editor shows one Operation overlay, and the overlay is the one account of a render
   from the press to its outcome - including the window before the accepted `202` has
   named an Operation to watch. Only the holder of the command knows that window exists,
   so the command lives where the overlay does and the panel is handed what it shows. */
export const useRenderApprovedRevision = ({
  approvedRevisionId,
  autoStart,
  onQueued,
  rendering,
}: {
  approvedRevisionId: string | null;
  /* True only in the render reached by this screen's just-completed approval. Reloading
     an older approved state remains passive, so a visit never queues artifact work by
     itself. */
  autoStart: boolean;
  /* The editor's watch: the accepted `202` is the earliest and most certain answer, so
     it goes there rather than waiting for the projection's next read. */
  onQueued: (operationId: string) => void;
  /* Whether the editor's watch already holds a render Operation, of any status. */
  rendering: boolean;
}) => {
  const queryClient = useQueryClient();
  const revisionQuery = useQuery({
    ...approvedRevisionQueryOptions(approvedRevisionId ?? ""),
    enabled: approvedRevisionId !== null,
  });
  const revision = approvedRevisionId === null ? undefined : revisionQuery.data;
  const renderKey = `render:${approvedRevisionId}`;

  const render = useMutation({
    mutationFn: async () => {
      if (revision === undefined) throw new Error("Render was offered before the revision loaded");
      return renderApprovedRevision(revision.id, revision.application_id, renderKey);
    },
    onSuccess: ({ operation }) => {
      queryClient.setQueryData(operationQueryKey(operation.id), operation);
      onQueued(operation.id);
    },
  });

  const ready = revision?.ready_qualified === true;
  const automaticAttempted = useRef(false);
  useEffect(() => {
    if (!autoStart || automaticAttempted.current || revision === undefined || ready) return;
    automaticAttempted.current = true;
    render.mutate();
  }, [autoStart, ready, render, revision]);

  /* `render.isPending` covers the moment before the accepted 202 has named an Operation to
     watch, and the auto-start branch covers the same window in the automatic path: with
     `autoStart` set the render always begins on mount. The one auto case that does not
     belong here is a 202 that never queued anything (`render.error`), which leaves no
     Operation to report - then the panel's own retry is the only way on. */
  const inFlight =
    approvedRevisionId !== null &&
    (rendering || render.isPending || (autoStart && !ready && render.error === null));

  return {
    inFlight,
    /* In flight with nothing yet recorded: the wait the overlay reports as pending. */
    pending: inFlight && !rendering,
    ready,
    render,
    revision,
    revisionError: approvedRevisionId === null ? null : revisionQuery.error,
  };
};

export type RenderApprovedRevision = ReturnType<typeof useRenderApprovedRevision>;
