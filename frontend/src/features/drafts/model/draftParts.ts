import type { EditableDocument } from "./drafts.types";

/* One part of the CV as the editor's navigation names it: the opening lines, or one
   section of the outline. */
export interface DraftPart {
  id: string;
  name: string;
  /* Holds a line nothing authorizes yet - one waiting on the reader's decision. */
  pending: boolean;
}

export const IDENTITY_PART = "identity";
export const sectionPartId = (index: number): string => `draft-section-${index}`;

/* The parts the outline is read in, in the CV's own order: the opening lines, then every
   section the projection named. Each says whether it still holds a line to decide. */
export const draftParts = (draft: EditableDocument): DraftPart[] => [
  {
    id: IDENTITY_PART,
    name: "פרטים",
    pending: [draft.outline.headline, ...draft.outline.contacts].some((claim) => claim.claim_type === "pending"),
  },
  ...draft.outline.sections.map((section, index) => ({
    id: sectionPartId(index),
    name: section.name,
    pending: section.claims.some((claim) => claim.claim_type === "pending"),
  })),
];

/* The part a claim sits in, so a jump to a line opens its part first. */
export const partOfClaim = (draft: EditableDocument, claimId: string): string | undefined => {
  if ([draft.outline.headline, ...draft.outline.contacts].some((claim) => claim.claim_id === claimId)) {
    return IDENTITY_PART;
  }
  const index = draft.outline.sections.findIndex((section) =>
    section.claims.some((claim) => claim.claim_id === claimId),
  );
  return index === -1 ? undefined : sectionPartId(index);
};

/* The part opened when the reader has not chosen one: the first section with a line
   waiting on them, as the design opens the editor - else the first section. The opening
   lines come first only when the outline has no section. */
export const defaultPart = (parts: DraftPart[]): string =>
  (parts.find((part) => part.id !== IDENTITY_PART && part.pending) ?? parts[1] ?? parts[0])?.id ?? IDENTITY_PART;
