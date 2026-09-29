import type { ClaimType } from "@/api/contracts";
import type { ClaimOrigin } from "./draftOverview";
import type { Tone } from "@/ui/tone";

/* Exhaustive over the generated union. A claim type added to the backend fails this
   build rather than reaching a screen as an untranslated value. This is the same reason
   `preparation_state` and `is_terminal` were typed at the boundary in the first place.

   Selection outcomes and omission reasons are the selection's vocabulary rather than the
   content's, and both the preparation screen and this editor say them, so they live
   with the selection in `@/features/preparation`. */

export const claimTypeLabels: Record<ClaimType, string> = {
  canonical: "מבוסס עובדה",
  composite: "מורכב מכמה עובדות",
  derived: "נוסח נגזר מעובדות",
  reviewed: "נבדק מול העובדות",
  pending: "ללא ביסוס",
  headline: "כותרת",
};

export const claimTypeTones: Record<ClaimType, Tone> = {
  canonical: "success",
  composite: "success",
  derived: "success",
  reviewed: "success",
  /* Free text nothing could authorize. A.4: it is preserved, marked unsafe at once, and
     blocks approval - not the save. */
  pending: "blocker",
  headline: "neutral",
};

export const claimTypeExplanations: Record<ClaimType, string> = {
  canonical: "השורה היא הנוסח המדויק של העובדה במאגר, בלי שינוי.",
  composite: "השורה מחברת כמה עובדות מהמאגר לשורה אחת לפי תבנית קבועה. העובדות עצמן לא השתנו.",
  derived: "השורה נגזרה מהעובדה לפי כלל ניסוח קבוע. המשמעות לא השתנתה.",
  reviewed: "השורה נוסחה מחדש לתפקיד, והניסוח נבדק בנפרד מול העובדות במאגר כדי לוודא שהמשמעות זהה.",
  pending: "אין עובדה שמאשרת את הטקסט הזה. הוא נשמר כפי שנכתב, ואינו מאפשר אישור של הגרסה.",
  headline: "שורת הכותרת של קורות החיים. היא נבנית מהפרופיל ולא מבחירת העובדות.",
};

/* Where a line came from, in the words the content summary counts it under. Keyed by
   `ClaimOrigin`, which folds the claim types into what the reader asks. */
export const claimOriginLabels: Record<ClaimOrigin, string> = {
  verbatim: "כלשון העובדה",
  reworded: "נוסח מחדש",
  unsupported: "ללא עובדה מאחוריה",
  structural: "מבנה המסמך",
};
