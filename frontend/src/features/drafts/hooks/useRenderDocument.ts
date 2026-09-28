import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useEffect, useRef } from "react";

import type { ApplicationDetail } from "@/api/contracts";
import { renderDocument } from "@/api/documents";
import { operationQueryKey } from "@/api/operations";

/* §16 `render_document`, held by the editor rather than by the panel that offers it.

   The editor shows one Operation overlay, and the overlay is the one account of a render
   from the press to its outcome - including the window before the accepted `202` has named
   an Operation to watch. Only the holder of the command knows that window exists, so the
   command lives where the overlay does and the panel is handed what it shows.

   Whether the document is approved or Ready is the projection's answer (`document_state`),
   never this hook's: it renders the hash the projection reports as approved. */
export const useRenderDocument = ({
  autoStart,
  detail,
  onQueued,
  rendering,
}: {
  /* True only right after this screen's own approval. Reloading an approved document stays
     passive, so a visit never queues render work by itself. */
  autoStart: boolean;
  detail: ApplicationDetail | undefined;
  /* The editor's watch: the accepted `202` is the earliest and most certain answer. */
  onQueued: (operationId: string) => void;
  /* Whether the editor's watch holds a render Operation that has not reached a terminal
     status - the run the overlay is already reporting. */
  rendering: boolean;
}) => {
  const queryClient = useQueryClient();
  const approved = detail?.document_state === "approved";
  const ready = detail?.document_state === "ready";
  const documentHash = approved ? (detail?.document_hash ?? null) : null;

  const render = useMutation({
    mutationFn: async () => {
      if (detail === undefined || documentHash === null) {
        throw new Error("Render was offered for a document that is not approved");
      }
      /* One key per approved document: a resent render of the same document is the same
         command, and a changed document is a different one. */
      return renderDocument(detail.application.id, documentHash, `render:${documentHash}`);
    },
    onSuccess: ({ operation }) => {
      queryClient.setQueryData(operationQueryKey(operation.id), operation);
      onQueued(operation.id);
    },
  });

  const automaticAttempted = useRef(false);
  useEffect(() => {
    if (!autoStart || automaticAttempted.current || documentHash === null) return;
    automaticAttempted.current = true;
    render.mutate();
  }, [autoStart, documentHash, render]);

  /* `render.isPending` covers the moment before the accepted 202 has named an Operation to
     watch, and the auto-start branch covers the tick before the effect above sends it. Once
     the command has settled either way, the watched Operation - or, for a 202 that queued
     nothing, the panel's own retry - is the account of the render. */
  const inFlight = rendering || render.isPending || (autoStart && !ready && render.isIdle);

  return {
    approved,
    inFlight,
    /* In flight with nothing yet recorded: the wait the overlay reports as pending. */
    pending: inFlight && !rendering,
    ready,
    render,
  };
};

export type RenderDocument = ReturnType<typeof useRenderDocument>;
