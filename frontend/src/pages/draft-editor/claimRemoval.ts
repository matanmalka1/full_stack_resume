import { outlineClaims } from "../../api/drafts";
import type { DraftClaim, WorkingDraft, WorkingDraftFacts } from "../../api/contracts";
import { type Removability, isStructuralStyle } from "./draftLabels";

const SHARED_LIMIT = 60;

const shorten = (text: string): string => (text.length <= SHARED_LIMIT ? text : `${text.slice(0, SHARED_LIMIT)}…`);

/* Which command, if any, removes this line.

   The first three answers are the backend's own refusals, restated here only so the
   control is absent rather than offered and refused: `remove_claim` rejects the headline
   and the contacts as structural, and rejects a claim the fact selection authorizes,
   naming `apply_selection_change`.

   The last two are this screen's, and are deliberately stricter than the server. Nothing
   stops `apply_selection_change` from excluding a shared fact or the fact behind a
   heading - it would simply do it, and change a line the user was not looking at. A
   `הסרה` whose effect cannot be described honestly is not offered. */
export const removability = (
  claim: DraftClaim,
  draft: WorkingDraft,
  facts: WorkingDraftFacts | undefined,
): Removability => {
  if (claim.claim_id === draft.outline.headline.claim_id) {
    return { route: "none", reason: "שורת הכותרת היא חלק ממבנה המסמך ואינה נמחקת." };
  }
  if (draft.outline.contacts.some((contact) => contact.claim_id === claim.claim_id)) {
    return {
      route: "none",
      reason: "פרטי הקשר נבנים מהפרופיל של המועמד ולא מתוכנית הבחירה, ולכן הם חוזרים בכל בנייה מחדש.",
    };
  }

  /* Free text nothing authorized: there is no fact to exclude, and its very presence
     refuses the deterministic path, so the patch is the only way out. */
  if (claim.claim_type === "pending" || claim.fact_ids.length === 0) {
    return { route: "patch" };
  }

  if (isStructuralStyle(claim.style)) {
    return {
      route: "none",
      reason: "השורה הזו נושאת את מבנה הסעיף ולא טענה בפני עצמה, ולכן היא אינה מוסרת בנפרד.",
    };
  }

  if (facts === undefined) {
    return { route: "none", reason: "חשבונאות העובדות עדיין נטענת." };
  }

  const byId = new Map(facts.facts.map((fact) => [fact.fact_id, fact]));
  const texts = new Map(outlineClaims(draft).map((line) => [line.claim_id, line.text]));

  for (const factId of claim.fact_ids) {
    const fact = byId.get(factId);

    if (fact === undefined || fact.outcome === null || fact.outcome === undefined) {
      return {
        route: "none",
        reason: "העובדה שמאחורי השורה אינה חלק מתוכנית הבחירה, ולכן אי אפשר להסיר אותה דרך שינוי הבחירה.",
      };
    }

    const shared = fact.linked_claim_ids.find((id) => id !== claim.claim_id);

    if (shared !== undefined) {
      const other = texts.get(shared);
      return {
        route: "none",
        reason:
          other === undefined
            ? "אחת העובדות של השורה משמשת גם שורה אחרת, והחרגה שלה הייתה משנה גם אותה."
            : `אחת העובדות של השורה משמשת גם את השורה «${shorten(other)}», והחרגה שלה הייתה משנה גם אותה.`,
      };
    }
  }

  return { route: "selection" };
};
