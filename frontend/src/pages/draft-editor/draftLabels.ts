import type { ClaimType, OmissionReason, SelectionOutcome } from "../../api/contracts";
import type { StatusTone } from "../../ui/status";

/* Exhaustive over the generated unions. A claim type, outcome, or omission reason added
   to the backend fails this build rather than reaching a screen as an untranslated value.
   This is the same reason `preparation_state` and `is_terminal` were typed at the
   boundary in the first place. */

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

export const selectionOutcomeLabels: Record<SelectionOutcome, string> = {
  pinned: "נקבעה במפורש",
  selected: "נבחרה",
  rescued: "הוחזרה לכיסוי דרישה",
  omitted: "לא נכללה",
};

export const omissionReasonLabels: Record<OmissionReason, string> = {
  below_section_budget: "לא נכנסה למכסת הסעיף",
  not_relevant_to_emphasis: "אינה רלוונטית לדגש הנוכחי",
  evicted_by_required_tag_rescue: "פינתה מקום לעובדה שנדרשה לכיסוי",
  not_in_profile_pool: "אינה במאגר של הפרופיל הזה",
  excluded_by_user: "הוחרגה על ידך",
};

/* A.4 frame 3 offers edit / regenerate / remove, and removal is two different commands.
   Which one - or neither - is decided per claim, so the reason a line cannot be removed
   is stated in place instead of a button being offered that would be refused. */
export type RemovalRoute = "patch" | "selection" | "none";

export interface Removability {
  route: RemovalRoute;
  /* Present only when the route is "none": why this line stays. */
  reason?: string;
}

/* Styles that carry a section's structure rather than a statement. Excluding the fact
   behind one of these deletes a heading or a date line, not a claim, so the exclusion
   control does not appear on them even though the plan ranked the fact. */
const STRUCTURAL_STYLES = new Set(["heading", "date", "contact", "headline"]);

export const isStructuralStyle = (style: string): boolean => STRUCTURAL_STYLES.has(style);
