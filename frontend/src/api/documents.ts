import { type QueryClient, queryOptions } from "@tanstack/react-query";

import { invalidateApplicationViews } from "./applications";
import { type ApiPath, apiRequest } from "./client";
import type {
  BuildFromAnalysisRequest,
  ClaimAddition,
  ClaimPatch,
  CreateDraftRequest,
  CVDocument,
  DecisionExport,
  DocumentActionRequest,
  DocumentCheck,
  DocumentMutation,
  DraftClaim,
  Operation,
  ProposeSelectionRequest,
  RegenerateDocumentClaimRequest,
  RegenerateDocumentSectionRequest,
  UpdateDocumentRequest,
  UpdateSelectionRequest,
} from "./contracts";
import { type QueuedOperation, queuedOperation } from "./operations";

/* §3/§14-§16: the one CV document of an Application, and every command addressed to it.

   The document is mutable and there is exactly one per Application, so it is keyed by the
   Application rather than by an id of its own. `document_hash` is its concurrency token:
   the read returns it as the ETag, the autosave PATCH sends it back as `If-Match`, and
   every other command carries it in the body as `expected_document_hash` (§21) - an action
   on a resource is not a conditional replacement of it. */

/* The editable structure the read derives from `content`. Absent until content exists
   (`ready_to_draft`), which is why the editor narrows to it before drawing anything. */
export type DocumentOutline = NonNullable<CVDocument["outline"]>;

/* The document and the token that authorizes writing to it, kept together.

   A read that returned only the body would leave the ETag to be captured somewhere else,
   and the one thing an optimistic save must never do is send a token that came from a
   different read than the content the user was looking at. */
export interface DocumentRead {
  document: CVDocument;
  etag: string | null;
}

export const documentQueryKey = (applicationId: string) => ["document", applicationId] as const;

const documentPath = (applicationId: string, suffix = ""): ApiPath =>
  `/api/v1/applications/${encodeURIComponent(applicationId)}/document${suffix}` as ApiPath;

/* `404` before the first analysis created the document, so callers enable this only
   once the projection names a `document_id`. */
export const documentQueryOptions = (applicationId: string) =>
  queryOptions({
    queryKey: documentQueryKey(applicationId),
    queryFn: async ({ signal }): Promise<DocumentRead> => {
      const response = await apiRequest<CVDocument>(documentPath(applicationId), { signal });
      return { document: response.data, etag: response.etag };
    },
  });

/* Every synchronous command that changes the document changes both its read and the §9
   projection that reports its state, so the two are refreshed together. The board is part
   of the Application views because it carries the same projection per row. */
export const invalidateDocumentViews = (queryClient: QueryClient, applicationId: string): Promise<unknown> =>
  Promise.all([
    queryClient.invalidateQueries({ queryKey: documentQueryKey(applicationId) }),
    invalidateApplicationViews(queryClient, applicationId),
  ]);

/* Every claim in the document, in reading order, headline and contacts included - the
   same set the backend walks, so the editor and the projection cannot disagree about what
   a claim is. */
export const outlineClaims = (outline: DocumentOutline): DraftClaim[] => [
  outline.headline,
  ...outline.contacts,
  ...outline.sections.flatMap((section) => section.claims),
];

/* The preview is framed, not fetched: the browser loads this URL inside a sandboxed
   iframe, so it never passes through `apiRequest` and never becomes a string this code
   holds. The hash is in the query string only so that a save produces a different URL and
   the frame reloads; the server ignores it and answers for the current document. */
export const documentPreviewSrc = (applicationId: string, documentHash: string): string =>
  `${documentPath(applicationId, "/preview")}?v=${encodeURIComponent(documentHash)}`;

/* Opened in a new tab rather than fetched, like the framed preview: the real PDF of the
   saved content, stamped as a draft and stored nowhere. The hash keeps a save from being
   answered by a cached older PDF. */
export const documentPreviewPdfHref = (applicationId: string, documentHash: string): string =>
  `${documentPath(applicationId, "/preview.pdf")}?v=${encodeURIComponent(documentHash)}`;

/* The rendered PDF of a Ready document (§16 `export_recruiter_pdf`). Opened, not fetched:
   the browser follows the link. The server computes the basis when it answers and refuses
   unless the document is Ready at that moment, so the link cannot hand over an outdated
   file even if the screen that drew it is. The hash in the query string only keeps a
   render from being answered by a cached earlier file; the server ignores it. */
export const documentPdfHref = (applicationId: string, documentHash: string): string =>
  `${documentPath(applicationId, "/pdf")}?v=${encodeURIComponent(documentHash)}`;

export interface DocumentPatch {
  claim_edits: ClaimPatch[];
  claim_removals: string[];
  claim_additions: ClaimAddition[];
  claim_orders?: Record<string, string[]>;
}

export interface DocumentSave {
  mutation: DocumentMutation;
  etag: string | null;
}

/* §14 `update_document`, the autosave. The ETag is the caller's, and the caller's
   obligation is that it came from the read whose content the user was editing. The
   generated request type marks the defaulted lists required; the patch sends them all. */
export const updateDocument = async (
  applicationId: string,
  etag: string,
  patch: DocumentPatch,
): Promise<DocumentSave> => {
  const body: Omit<UpdateDocumentRequest, "claim_orders"> & Partial<Pick<UpdateDocumentRequest, "claim_orders">> =
    patch;
  const response = await apiRequest<DocumentMutation>(documentPath(applicationId), {
    method: "PATCH",
    body,
    etag,
  });
  return { mutation: response.data, etag: response.etag };
};

export interface SelectionOverlay {
  pinned_fact_ids: string[];
  excluded_fact_ids: string[];
}

/* The document's own overlay, read back from the selection rather than remembered in
   component state. Both lists are absolute, not deltas: `update_selection` replaces the
   overlay with what it is sent, so a change that sent only what moved would silently drop
   every earlier decision. */
export const selectionOverlay = (document: CVDocument): SelectionOverlay => ({
  pinned_fact_ids: [...document.selection.pinned_fact_ids],
  excluded_fact_ids: [...document.selection.excluded_fact_ids],
});

/* §14 `update_selection`: synchronous and deterministic. With content present it updates
   selection and content together, or refuses with `412` when the change needs wording
   judgment - which is the case §14 sends to regeneration. `emphasis_override` is sent only
   when it is being decided: absent means "leave the effective Emphasis as it is". */
export const updateSelection = async (
  applicationId: string,
  expectedDocumentHash: string,
  overlay: SelectionOverlay,
  emphasisOverride?: NonNullable<UpdateSelectionRequest["emphasis_override"]>,
): Promise<DocumentMutation> => {
  const body: UpdateSelectionRequest = {
    expected_document_hash: expectedDocumentHash,
    ...overlay,
    ...(emphasisOverride === undefined ? {} : { emphasis_override: emphasisOverride }),
  };
  const response = await apiRequest<DocumentMutation>(documentPath(applicationId, "/selection"), {
    method: "POST",
    body,
  });
  return response.data;
};

/* §14 `propose_selection`: an AI Operation whose output is only a Proposal. Activation
   repeats `update_selection`'s checks and discards the result if the document moved. */
export const proposeSelection = async (
  applicationId: string,
  expectedDocumentHash: string,
  idempotencyKey: string,
): Promise<QueuedOperation> => {
  const body: Omit<ProposeSelectionRequest, "provider"> = { expected_document_hash: expectedDocumentHash };
  return queuedOperation(
    await apiRequest<Operation>(documentPath(applicationId, "/selection-proposals"), {
      method: "POST",
      body,
      idempotencyKey,
    }),
  );
};

/* §14 `build_from_analysis`: synchronous. Re-pins the document to the named analysis with
   that analysis's deterministic selection and no content, and clears every stamp. The
   analysis is named by the caller - it is the one the screen offered - never resolved by
   the server. */
export const buildFromAnalysis = async (
  applicationId: string,
  expectedDocumentHash: string,
  analysisId: string,
): Promise<DocumentMutation> => {
  const body: BuildFromAnalysisRequest = { expected_document_hash: expectedDocumentHash, analysis_id: analysisId };
  const response = await apiRequest<DocumentMutation>(documentPath(applicationId, "/build-from-analysis"), {
    method: "POST",
    body,
  });
  return response.data;
};

/* §14 `create_draft`: asynchronous, and always an AI run. Activation writes content only
   while the document still carries the hash this call was addressed to. */
export const createDraft = async (
  applicationId: string,
  expectedDocumentHash: string,
  idempotencyKey: string,
): Promise<QueuedOperation> => {
  const body: CreateDraftRequest = {
    expected_document_hash: expectedDocumentHash,
    provider: "openai",
  };
  return queuedOperation(
    await apiRequest<Operation>(documentPath(applicationId, "/draft"), {
      method: "POST",
      body,
      idempotencyKey,
    }),
  );
};

/* §14 regeneration: an AI Operation over one exact document. An autosave that lands while
   the provider is answering changes the hash, so activation discards the result rather
   than overwriting the user's edit. `instruction` is omitted: the server defaults it. */
export const regenerateSection = async (
  document: CVDocument,
  section: string,
  idempotencyKey: string,
): Promise<QueuedOperation> => {
  const body: Omit<RegenerateDocumentSectionRequest, "instruction"> = {
    expected_document_hash: document.document_hash,
    section,
  };
  return queuedOperation(
    await apiRequest<Operation>(documentPath(document.application_id, "/regenerate-section"), {
      method: "POST",
      body,
      idempotencyKey,
    }),
  );
};

/* `keepText` reviews the user's own wording instead of writing new wording: the claim's
   current text goes to semantic review against its own facts (product spec §10). */
export const regenerateClaim = async (
  document: CVDocument,
  claimId: string,
  idempotencyKey: string,
  keepText = false,
): Promise<QueuedOperation> => {
  const body: Omit<RegenerateDocumentClaimRequest, "instruction"> = {
    expected_document_hash: document.document_hash,
    claim_id: claimId,
    keep_text: keepText,
  };
  return queuedOperation(
    await apiRequest<Operation>(documentPath(document.application_id, "/regenerate-claim"), {
      method: "POST",
      body,
      idempotencyKey,
    }),
  );
};

const documentAction = async <T>(applicationId: string, suffix: string, expectedDocumentHash: string): Promise<T> => {
  const body: DocumentActionRequest = { expected_document_hash: expectedDocumentHash };
  const response = await apiRequest<T>(documentPath(applicationId, suffix), { method: "POST", body });
  return response.data;
};

/* §15 `check_document`: synchronous deterministic validation. A failed check is `200`
   with `passed=false` - the report is data, not an exception. */
export const checkDocument = (applicationId: string, expectedDocumentHash: string): Promise<DocumentCheck> =>
  documentAction<DocumentCheck>(applicationId, "/check", expectedDocumentHash);

/* §15 `approve_document`: synchronous. It runs the same check and approves only when it
   passed; a failed check comes back as data, and a blocker as a `412` naming it. */
export const approveDocument = (applicationId: string, expectedDocumentHash: string): Promise<DocumentCheck> =>
  documentAction<DocumentCheck>(applicationId, "/approve", expectedDocumentHash);

/* §16 `render_document`: asynchronous. Admission requires the document to be approved;
   activation requires it to still carry the hash this call names. */
export const renderDocument = async (
  applicationId: string,
  expectedDocumentHash: string,
  idempotencyKey: string,
): Promise<QueuedOperation> => {
  const body: DocumentActionRequest = { expected_document_hash: expectedDocumentHash };
  return queuedOperation(
    await apiRequest<Operation>(documentPath(applicationId, "/render"), {
      method: "POST",
      body,
      idempotencyKey,
    }),
  );
};

/* §16 `export_decision_markdown`: the provenance export of the current document. Keyed by
   the hash, because it describes the document as it stands and a changed document is a
   different export. */
export const decisionExportQueryOptions = (applicationId: string, documentHash: string) =>
  queryOptions({
    queryKey: ["decision-export", applicationId, documentHash] as const,
    queryFn: async ({ signal }): Promise<DecisionExport> =>
      (await apiRequest<DecisionExport>(documentPath(applicationId, "/decision-markdown"), { signal })).data,
  });
