import type { ApplicationDetail, ClaimType, DraftClaim } from "@/api/contracts";
import { outlineClaims } from "@/api/documents";
import type { EditableDocument } from "./drafts.types";

/* Where a line of the draft came from, in the reader's terms rather than the claim type's.

   The claim type is the validator's vocabulary - five ways a line can be authorized. What
   the reader asks of a tailored CV is simpler: is this line the fact as written, was it
   reworded for the role, or does nothing stand behind it. Rewording is allowed (the fact
   and its meaning stay the same); an unsupported line blocks approval. */
export type ClaimOrigin = "verbatim" | "reworded" | "unsupported" | "structural";

const originByType: Record<ClaimType, ClaimOrigin> = {
  canonical: "verbatim",
  composite: "reworded",
  derived: "reworded",
  reviewed: "reworded",
  pending: "unsupported",
  headline: "structural",
};

const claimOrigin = (claim: DraftClaim): ClaimOrigin => originByType[claim.claim_type];

export interface ContentSummary {
  /* Counts over the document's sections - the tailored body, not the headline and contacts. */
  verbatim: number;
  reworded: number;
  unsupported: number;
  /* Every unsupported line in reading order, headline and contacts included: each one
     blocks approval wherever it sits. */
  unsupportedClaims: DraftClaim[];
}

export const summarizeContent = (draft: EditableDocument): ContentSummary => {
  const body = draft.outline.sections.flatMap((section) => section.claims);
  const count = (origin: ClaimOrigin) => body.filter((claim) => claimOrigin(claim) === origin).length;
  return {
    verbatim: count("verbatim"),
    reworded: count("reworded"),
    unsupported: count("unsupported"),
    unsupportedClaims: outlineClaims(draft.outline).filter((claim) => claimOrigin(claim) === "unsupported"),
  };
};

export interface SelectionSummary {
  /* Facts the selection put into the document, whichever way it decided. */
  included: number;
  /* Of those, the ones fixed by an explicit decision rather than the ranking. */
  pinned: number;
  /* Facts the selection weighed and left out, with nothing in the draft resting on them. */
  omitted: EditableDocument["facts"];
}

/* The selection's accounting, read from the document's own `facts`. Only facts the
   selection actually ranked count: `outcome` is null for a fact nothing weighed, such as
   a contact line's source. */
export const summarizeSelection = (draft: EditableDocument): SelectionSummary => {
  const ranked = draft.facts.filter((fact) => fact.outcome !== null && fact.outcome !== undefined);
  return {
    included: ranked.filter((fact) => fact.outcome !== "omitted").length,
    pinned: ranked.filter((fact) => fact.outcome === "pinned").length,
    omitted: ranked.filter((fact) => fact.outcome === "omitted" && fact.linked_claim_ids.length === 0),
  };
};

/* The three things this step is made of, in the order the reader does them. */
export type DraftStepId = "review" | "check" | "approve";
type DraftStepStatus = "done" | "current" | "blocked" | "upcoming";

interface DraftStep {
  id: DraftStepId;
  status: DraftStepStatus;
}

/* Where the reader stands inside the draft step.

   A restatement of the projection, not a second workflow: approval and readiness are
   `preparation_state`, the check is `content_check`, and the only thing read from the
   document itself is whether any line still has nothing behind it - which the validator
   refuses anyway. Nothing here gates a command; the commands' own availability does. */
export const draftSteps = (detail: ApplicationDetail, content: ContentSummary): DraftStep[] => {
  const approved = detail.preparation_state === "approved" || detail.preparation_state === "ready";
  const blocked = content.unsupportedClaims.length > 0 || detail.review_reasons.length > 0;
  const checked = detail.content_check === "passed";

  const review: DraftStepStatus = approved || !blocked ? "done" : "blocked";
  const check: DraftStepStatus = approved || (checked && !blocked) ? "done" : blocked ? "upcoming" : "current";
  const approve: DraftStepStatus = approved ? "done" : checked && !blocked ? "current" : "upcoming";

  return [
    { id: "review", status: review },
    { id: "check", status: check },
    { id: "approve", status: approve },
  ];
};
