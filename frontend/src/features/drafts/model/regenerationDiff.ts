import type { DraftClaim } from "@/api/contracts";
import { type DocumentOutline, outlineClaims } from "@/api/documents";

/* What a regeneration was asked to rewrite. */
export type RegenerationTarget = { kind: "claim"; claimId: string } | { kind: "section"; section: string };

/* The lines a regeneration may overwrite, as they read before it was queued. Kept on the
   client only: the server keeps no earlier wording to compare with, and the diff is the
   reader's, not a record. */
export interface RegenerationSnapshot {
  target: RegenerationTarget;
  documentHash: string;
  claims: DraftClaim[];
}

/* One line the regeneration changed: the wording before and the wording it wrote. */
export interface RegenerationChange {
  claimId: string;
  before: DraftClaim;
  after: DraftClaim;
}

/* Where one changed line stands now, against the draft on screen:
   - `regenerated`: still the wording the regeneration wrote, so it can be reverted;
   - `reverted`: back to the wording before;
   - `edited`: changed again since, by hand or by undo - a revert would overwrite that;
   - `gone`: no longer in the draft. */
export type RegenerationChangeState = "regenerated" | "reverted" | "edited" | "gone";

const sectionOf = (outline: DocumentOutline, name: string) => outline.sections.find((section) => section.name === name);

const targetClaims = (outline: DocumentOutline, target: RegenerationTarget): DraftClaim[] =>
  target.kind === "section"
    ? (sectionOf(outline, target.section)?.claims ?? [])
    : outlineClaims(outline).filter((claim) => claim.claim_id === target.claimId);

export const takeSnapshot = (
  outline: DocumentOutline,
  documentHash: string,
  target: RegenerationTarget,
): RegenerationSnapshot => ({
  target,
  documentHash,
  claims: structuredClone(targetClaims(outline, target)),
});

/* The lines whose wording the regeneration changed, matched by claim id - a regeneration
   rewrites the lines it is given in place rather than minting new ones. A line whose text
   is unchanged is not a change, whatever else the run did to it. */
export const regenerationChanges = (snapshot: RegenerationSnapshot, outline: DocumentOutline): RegenerationChange[] => {
  const current = new Map(outlineClaims(outline).map((claim) => [claim.claim_id, claim]));
  return snapshot.claims.flatMap((before) => {
    const after = current.get(before.claim_id);
    return after === undefined || after.text === before.text
      ? []
      : [{ claimId: before.claim_id, before, after: structuredClone(after) }];
  });
};

export const changeState = (change: RegenerationChange, outline: DocumentOutline): RegenerationChangeState => {
  const current = outlineClaims(outline).find((claim) => claim.claim_id === change.claimId);
  if (current === undefined) return "gone";
  if (current.text === change.after.text) return "regenerated";
  if (current.text === change.before.text) return "reverted";
  return "edited";
};

/* The edit a revert sends: the earlier wording with the earlier fact links, addressed to
   the line as it is now. It is an ordinary edit through autosave - If-Match and the
   server's own content checks decide what the line becomes, exactly as for typed text. */
export const revertEdit = (
  change: RegenerationChange,
  outline: DocumentOutline,
): { claim: DraftClaim; text: string } | null => {
  if (changeState(change, outline) !== "regenerated") return null;
  const current = outlineClaims(outline).find((claim) => claim.claim_id === change.claimId);
  if (current === undefined) return null;
  return { claim: { ...current, fact_ids: [...change.before.fact_ids] }, text: change.before.text };
};
