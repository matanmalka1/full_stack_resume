import type { ClaimType } from "@/api/contracts";
import type { StatusTone } from "@/ui/status";

/* Exhaustive over the generated union. A claim type added to the backend fails this
   build rather than reaching a screen as an untranslated value. This is the same reason
   `preparation_state` and `is_terminal` were typed at the boundary in the first place.

   Selection outcomes and omission reasons are the SelectionPlan's vocabulary rather than
   the draft's, and both the preparation screen and this editor say them, so they live
   with the plan in `@/features/applications/model/selectionLabels`. */

export const claimTypeLabels: Record<ClaimType, string> = {
  canonical: "מבוסס עובדה",
  composite: "מורכב מכמה עובדות",
  derived: "נוסח נגזר מעובדות",
  pending: "ללא ביסוס",
  headline: "כותרת",
};

export const claimTypeTones: Record<ClaimType, StatusTone> = {
  canonical: "success",
  composite: "success",
  derived: "success",
  /* Free text nothing could authorize. A.4: it is preserved, marked unsafe at once, and
     blocks approval - not the save. */
  pending: "blocker",
  headline: "neutral",
};

export const claimTypeExplanations: Record<ClaimType, string> = {
  canonical: "הטקסט הוא הניסוח הקנוני של העובדה שמתחתיו.",
  composite: "הטקסט מחבר כמה עובדות לפי תבנית קבועה.",
  derived: "הטקסט נגזר מהעובדות שמתחתיו לפי כלל ניסוח.",
  pending: "אין עובדה שמאשרת את הטקסט הזה. הוא נשמר כפי שנכתב, ואינו מאפשר אישור של הגרסה.",
  headline: "שורת הכותרת של קורות החיים.",
};
