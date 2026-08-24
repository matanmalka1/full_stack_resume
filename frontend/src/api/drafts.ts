import { queryOptions } from "@tanstack/react-query";

import { type ApiPath, apiRequest } from "./client";
import { type QueuedOperation, queuedOperation } from "./operations";
import type {
  ApplySelectionChangeRequest,
  ClaimPatch,
  DraftClaim,
  Operation,
  RegenerateClaimRequest,
  RegenerateSectionRequest,
  SelectionChange,
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

/* The overlay the next SelectionPlan is built from. Both lists are absolute, not deltas:
   `apply_selection_change` hands them to `create_selection_plan`, which plans from them
   alone, so a change that sent only what moved would silently drop every earlier
   decision. They are read back out of the accounting rather than remembered in component
   state, which is what keeps them true after a reload. */
export const selectionOverlay = (
  facts: WorkingDraftFacts,
): { pinned_fact_ids: string[]; excluded_fact_ids: string[] } => ({
  pinned_fact_ids: facts.facts
    .filter((fact) => fact.outcome === "pinned")
    .map((fact) => fact.fact_id),
  excluded_fact_ids: facts.facts
    .filter((fact) => fact.reason === "excluded_by_user")
    .map((fact) => fact.fact_id),
});

/* §14: a deterministic re-selection. `201` because the change creates an immutable
   SelectionPlan and rebuilds the draft from it in one write - there is no Operation to
   poll and no `Location` to verify.

   A draft carrying manual wording is a `412`: a deterministic rebuild would replace the
   user's own sentences with the engine's, which is the case §14 sends to regeneration. */
export const applySelectionChange = async (
  workingDraftId: string,
  expectedEditVersion: number,
  overlay: { pinned_fact_ids: string[]; excluded_fact_ids: string[] },
): Promise<SelectionChange> => {
  const body: ApplySelectionChangeRequest = {
    expected_edit_version: expectedEditVersion,
    ...overlay,
  };
  const response = await apiRequest<SelectionChange>(
    `${workingDraftPath(workingDraftId)}/apply-selection-change` as ApiPath,
    { method: "POST", body },
  );

  return response.data;
};

/* §14 regeneration: an AI Operation over one exact draft version.

   All three parts of the draft's identity are sent - ID, `edit_version`, and content hash
   - because that is what the Operation freezes. An autosave that lands while the provider
   is answering makes activation fail as `SOURCE_CHANGED` rather than overwriting the
   user's edit, and that is the behaviour these arguments buy.

   The analysis and the plan are explicit for the same reason `create_draft` names them: a
   regeneration that resolved them for itself could rewrite a section against a plan the
   user never saw. `provider` is omitted, as everywhere else, because the server owns that
   default. */
const regenerate = async (
  path: ApiPath,
  /* `instruction` is omitted rather than sent empty: the server defaults it, and
     restating a default here would be a second copy of a policy this client does not
     own. The `Omit` still binds every field name to the generated contract. */
  body: Omit<RegenerateSectionRequest, "instruction"> | Omit<RegenerateClaimRequest, "instruction">,
  idempotencyKey: string,
): Promise<QueuedOperation> =>
  queuedOperation(await apiRequest<Operation>(path, { method: "POST", body, idempotencyKey }));

export const regenerateSection = async (
  draft: WorkingDraft,
  section: string,
  idempotencyKey: string,
): Promise<QueuedOperation> =>
  regenerate(
    `${workingDraftPath(draft.id)}/regenerate-section` as ApiPath,
    {
      application_id: draft.application_id,
      expected_edit_version: draft.edit_version,
      expected_content_hash: draft.content_hash,
      job_analysis_id: draft.job_analysis_id,
      selection_plan_id: draft.selection_plan_id,
      section,
    },
    idempotencyKey,
  );

export const regenerateClaim = async (
  draft: WorkingDraft,
  claimId: string,
  idempotencyKey: string,
): Promise<QueuedOperation> =>
  regenerate(
    `${workingDraftPath(draft.id)}/regenerate-claim` as ApiPath,
    {
      application_id: draft.application_id,
      expected_edit_version: draft.edit_version,
      expected_content_hash: draft.content_hash,
      job_analysis_id: draft.job_analysis_id,
      selection_plan_id: draft.selection_plan_id,
      claim_id: claimId,
    },
    idempotencyKey,
  );
