import type { DraftClaim, DraftFact } from "@/api/contracts";
import type { DocumentFacts, EditableDocument } from "./drafts.types";

/* A.4 frame 3 offers edit / regenerate / remove. Whether a line can be removed is decided
   per claim, so the reason a line cannot be removed is stated in place instead of a button
   being offered that would be refused. */
type RemovalRoute = "patch" | "none";

export interface Removability {
  route: RemovalRoute;
  /* Present only when the route is "none": why this line stays. */
  reason?: string;
}

/* Styles that carry a section's structure rather than a statement: a heading or a date is
   what keeps a role's lines attributed to it. */
const STRUCTURAL_STYLES = new Set(["heading", "date", "contact", "headline"]);

/* The facts the accounting says stand behind one line, in the order the accounting
   reports them. */
export const linkedFacts = (claim: DraftClaim, facts: DocumentFacts | undefined): DraftFact[] =>
  (facts?.facts ?? []).filter((fact) => claim.fact_ids.includes(fact.fact_id));

/* Whether this line can be removed, restating the backend's refusals only so the control
   is absent rather than offered and refused: `remove_claim` rejects the headline, the
   contacts, and headings and dates as structure. Any other line may go - the document holds
   no separate fact selection, so the facts it linked simply stop being used. */
export const removability = (claim: DraftClaim, draft: EditableDocument): Removability => {
  if (claim.claim_id === draft.outline.headline.claim_id) {
    return { route: "none", reason: "שורת הכותרת היא חלק ממבנה המסמך ואינה נמחקת." };
  }
  /* No reason on the row: every contact line shares it, so `DraftIdentityCard` says it
     once for all of them instead of under each. */
  if (draft.outline.contacts.some((contact) => contact.claim_id === claim.claim_id)) {
    return { route: "none" };
  }
  if (claim.claim_type !== "pending" && STRUCTURAL_STYLES.has(claim.style)) {
    return {
      route: "none",
      reason: "השורה הזו נושאת את מבנה הסעיף ולא טענה בפני עצמה, ולכן היא אינה מוסרת בנפרד.",
    };
  }
  return { route: "patch" };
};
