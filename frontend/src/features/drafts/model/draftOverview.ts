import type { DraftClaim } from "@/api/contracts";
import { outlineClaims } from "@/api/documents";
import type { EditableDocument } from "./drafts.types";

/* Every line nothing authorizes, in reading order, headline and contacts included: each
   one blocks approval wherever it sits. */
export const unsupportedClaims = (draft: EditableDocument): DraftClaim[] =>
  outlineClaims(draft.outline).filter((claim) => claim.claim_type === "pending");
