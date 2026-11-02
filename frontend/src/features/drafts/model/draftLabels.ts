import type { ClaimType } from "@/api/contracts";

/* Exhaustive over the generated union. A claim type added to the backend fails this
   build rather than reaching a screen as an untranslated value. This is the same reason
   `preparation_state` and `is_terminal` were typed at the boundary in the first place.

   Selection outcomes and omission reasons are the selection's vocabulary rather than the
   content's, and both the preparation screen and this editor say them, so they live
   with the selection in `@/features/preparation`. */

/* Where a line came from, in the few words its row's status line spends on it, as the
   design words it: a line copied, combined or derived from facts is "from the pool"; one
   reworded for the role says it was checked; free text says it has nothing behind it. */
export const claimTypeLabels: Record<ClaimType, string> = {
  canonical: "מתוך המאגר",
  composite: "משולב מכמה עובדות",
  derived: "נגזר מהמאגר",
  reviewed: "נוסח מחדש ונבדק",
  pending: "ללא ביסוס",
  headline: "מהפרופיל",
};

export const claimTypeExplanations: Record<ClaimType, string> = {
  canonical: "השורה היא הנוסח המדויק של העובדה במאגר, בלי שינוי.",
  composite: "השורה מחברת כמה עובדות מהמאגר לשורה אחת לפי תבנית קבועה. העובדות עצמן לא השתנו.",
  derived: "השורה נגזרה מהעובדה לפי כלל ניסוח קבוע. המשמעות לא השתנתה.",
  reviewed: "השורה נוסחה מחדש לתפקיד, והניסוח נבדק בנפרד מול העובדות במאגר כדי לוודא שהמשמעות זהה.",
  pending: "אין עובדה שמאשרת את הטקסט הזה. הוא נשמר כפי שנכתב, ואינו מאפשר אישור של הגרסה.",
  headline: "שורת הכותרת של קורות החיים. היא נבנית מהפרופיל ולא מהעובדות שנבחרו לטיוטה.",
};
