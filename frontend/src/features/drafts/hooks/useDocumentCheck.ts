import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";

import { applicationDetailQueryOptions, invalidateApplicationViews } from "@/api/applications";
import type { ContentCheck, DocumentCheck, ValidationReport } from "@/api/contracts";
import { checkDocument, documentQueryKey, documentQueryOptions } from "@/api/documents";
import type { EditableDocument } from "../model/drafts.types";

export interface DocumentCheckState {
  /* The stored report's standing against the current document, as the server computed it
     (§5). `outdated` is still shown - as outdated - and authorizes nothing. */
  contentCheck: ContentCheck;
  error: unknown;
  isPending: boolean;
  /* The check this screen just ran, while it still describes the document on screen. */
  lastCheck: DocumentCheck | undefined;
  /* True when the server says the stored report passed against this exact document, and
     nothing on screen has moved past it. The only condition approval is offered on. */
  passing: boolean;
  report: ValidationReport | null;
  /* An approval was refused because the document changed (`DOCUMENT_CHANGED`). Reported
     rather than derived: the screen believed the document current, or approval would not
     have been offered. Running a new check is the answer, so that is what clears it. */
  reportStaleRefusal: () => void;
  stale: boolean;
  checkExact: (current: EditableDocument) => Promise<DocumentCheck>;
}

/* §15 `check_document` and its result, beside the document it describes rather than on a
   screen of its own. There is no run to look up: the report is stored on the document with
   the basis it was produced for, so whether it is current is the read's own answer. */
export const useDocumentCheck = (
  applicationId: string,
  draft: EditableDocument | undefined,
  unavailable = false,
): DocumentCheckState => {
  const queryClient = useQueryClient();
  const [stale, setStale] = useState(false);

  const mutation = useMutation({
    mutationFn: (current: EditableDocument) => checkDocument(applicationId, current.document_hash),
    onSuccess: async () => {
      await invalidateApplicationViews(queryClient, applicationId);
      await queryClient.cancelQueries({ queryKey: documentQueryKey(applicationId) });
      await Promise.all([
        queryClient.fetchQuery({ ...documentQueryOptions(applicationId), staleTime: 0 }),
        queryClient.fetchQuery({ ...applicationDetailQueryOptions(applicationId), staleTime: 0 }),
      ]);
    },
  });

  // A late result cannot describe a newer edit: it counts only for the document it names.
  const lastCheck =
    mutation.data !== undefined && draft !== undefined && mutation.data.document_hash === draft.document_hash
      ? mutation.data
      : undefined;
  const contentCheck = draft?.content_check ?? "none";
  const report = unavailable ? null : (draft?.content_report ?? null);

  return {
    contentCheck: unavailable && contentCheck !== "none" ? "outdated" : contentCheck,
    error: mutation.error,
    isPending: mutation.isPending,
    lastCheck,
    passing: !unavailable && !stale && contentCheck === "passed",
    report,
    reportStaleRefusal: () => setStale(true),
    stale,
    checkExact: (current) => {
      setStale(false);
      return mutation.mutateAsync(current);
    },
  };
};
