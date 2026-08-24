import { queryOptions } from "@tanstack/react-query";

import { type ApiPath, apiRequest } from "./client";
import type {
  ClaimPatch,
  DraftClaim,
  WorkingDraft,
  WorkingDraftFacts,
  WorkingDraftUpdate,
} from "./contracts";

/* The draft and the token that authorizes writing to it, kept together.

   A read that returned only the body would leave the ETag to be captured somewhere else,
   and the one thing an optimistic save must never do is send a token that came from a
   different read than the content the user was looking at. */
export interface DraftRead {
  draft: WorkingDraft;
  etag: string | null;
}

export const workingDraftQueryKey = (workingDraftId: string) =>
  ["working-draft", workingDraftId] as const;

export const workingDraftFactsQueryKey = (workingDraftId: string) =>
  ["working-draft-facts", workingDraftId] as const;

const workingDraftPath = (workingDraftId: string): ApiPath =>
  `/api/v1/working-drafts/${encodeURIComponent(workingDraftId)}`;

export const workingDraftQueryOptions = (workingDraftId: string) =>
  queryOptions({
    queryKey: workingDraftQueryKey(workingDraftId),
    queryFn: async ({ signal }): Promise<DraftRead> => {
      const response = await apiRequest<WorkingDraft>(workingDraftPath(workingDraftId), { signal });
      return { draft: response.data, etag: response.etag };
    },
  });

/* §20 candidate accounting. Separate from the draft read because it answers a different
   question - what backs a line, and what could be added to one - and because the fact
   renderings are Knowledge, which moves on its own schedule rather than with an edit. */
export const workingDraftFactsQueryOptions = (workingDraftId: string) =>
  queryOptions({
    queryKey: workingDraftFactsQueryKey(workingDraftId),
    queryFn: async ({ signal }) => {
      const response = await apiRequest<WorkingDraftFacts>(
        `${workingDraftPath(workingDraftId)}/facts` as ApiPath,
        { signal },
      );
      return response.data;
    },
  });

/* The preview is framed, not fetched: the browser loads this URL inside a sandboxed
   iframe, so it never passes through `apiRequest` and never becomes a string this code
   holds. The version is in the query string only so that a save produces a different URL
   and the frame reloads; the server ignores it and answers for the current version. */
export const draftPreviewSrc = (workingDraftId: string, editVersion: number): string =>
  `${workingDraftPath(workingDraftId)}/preview?v=${editVersion}`;

/* Every claim in the document, in reading order, headline and contacts included - the
   same set `draft_claims` walks on the backend, so the editor and the projection cannot
   disagree about what a claim is. */
export const outlineClaims = (draft: WorkingDraft): DraftClaim[] => [
  draft.outline.headline,
  ...draft.outline.contacts,
  ...draft.outline.sections.flatMap((section) => section.claims),
];

export interface DraftPatch {
  claim_edits: ClaimPatch[];
  claim_removals: string[];
}

export interface DraftUpdate {
  update: WorkingDraftUpdate;
  etag: string | null;
}

/* §14 autosave. The ETag is the caller's, and the caller's obligation is that it came
   from the read whose content the user was editing - `If-Match: *` is refused by the
   server precisely because a save that matched anything is the lost update the header
   exists to prevent. */
export const updateWorkingDraft = async (
  workingDraftId: string,
  etag: string,
  patch: DraftPatch,
): Promise<DraftUpdate> => {
  const response = await apiRequest<WorkingDraftUpdate>(workingDraftPath(workingDraftId), {
    method: "PATCH",
    body: patch,
    etag,
  });

  return { update: response.data, etag: response.etag };
};
