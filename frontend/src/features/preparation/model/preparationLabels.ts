import type { PreparationState } from "@/api/contracts";
import { BadgeCheck, CircleCheck, Clock, FilePen, FilePlus2, type LucideIcon } from "lucide-react";

import type { Tone } from "@/ui/tone";

/* Keyed by the generated unions, so a state added to the §9 projection fails the
   frontend build instead of reaching the screen untranslated. */
export const preparationStateLabels: Record<PreparationState, string> = {
  needs_analysis: "ממתין לניתוח המשרה",
  ready_to_draft: "מוכן ליצירת טיוטה",
  draft_in_progress: "טיוטה בעבודה",
  approved: "אושר, ממתין ליצירת הקובץ",
  ready: "קורות החיים מוכנים",
};

/* A.2: a state is never colour alone. The tone adds the icon and the Hebrew status word
   the badge already carries. */
export const preparationStateTones: Record<PreparationState, Tone> = {
  needs_analysis: "neutral",
  ready_to_draft: "neutral",
  draft_in_progress: "neutral",
  approved: "success",
  ready: "success",
};

/* Hebrew names for the actions the projection reports. Deliberately a partial map over
   an open set of strings rather than a Record over an enum this layer invented: the
   action vocabulary is the backend's, `available_actions` mixes preparation commands
   with review-reason resolution actions, and an action with no name here is reported as
   itself rather than guessed at. */
const actionLabels: Record<string, string> = {
  analyze: "ניתוח המשרה",
  edit_matching_configuration: "עריכת הגדרות ההתאמה",
  build_from_analysis: "בנייה מחדש מהניתוח החדש",
  update_selection: "בחירת העובדות",
  propose_selection: "הצעת בחירה מ־AI",
  confirm_and_use_fact: "אישור עובדה ושימוש בה",
  create_draft: "יצירת טיוטה",
  edit: "עריכת הטיוטה",
  regenerate_section: "יצירה מחדש של פרק",
  regenerate_claim: "יצירה מחדש של טענה",
  check: "בדיקת הטיוטה",
  approve: "אישור הגרסה",
  render: "יצירת קובץ קורות החיים",
  submit: "רישום ההגשה",
  download_pdf: "הורדת ה־PDF",
};

export const actionLabel = (action: string): string => actionLabels[action] ?? action;

/* One fixed sentence per action: what the step is, for the board row that recommends
   it. It describes the step in general - never this Application's state - so it can
   claim nothing the projection has not said. Keyed like `actionLabels`; the test that
   reads the backend's action vocabulary requires both for every action. */
const actionDescriptions: Record<string, string> = {
  analyze: "קריאת דרישות המשרה ובדיקה אילו עובדות מאושרות עונות עליהן.",
  edit_matching_configuration: "עדכון הגדרות ההתאמה לפני בחירת העובדות.",
  build_from_analysis: "קיים ניתוח חדש יותר מזה שהמסמך בנוי עליו, ואפשר לבנות ממנו את המסמך מחדש.",
  update_selection: "בחירת העובדות המאושרות שייכנסו לקורות החיים עבור המשרה.",
  propose_selection: "בקשה מ־AI להציע אילו עובדות ייכנסו לקורות החיים.",
  confirm_and_use_fact: "עובדה ממתינה לאישור לפני שאפשר להשתמש בה בטיוטה.",
  create_draft: "יצירת טיוטה ראשונה מהעובדות שנבחרו.",
  edit: "הטיוטה פתוחה לעריכה ועדיין לא אושרה.",
  regenerate_section: "יצירה מחדש של פרק בטיוטה מאותן עובדות.",
  regenerate_claim: "יצירה מחדש של טענה בטיוטה מאותה עובדה.",
  check: "בדיקת הטיוטה מול העובדות לפני האישור.",
  approve: "הטיוטה מוכנה לבדיקה ולאישור שלך.",
  render: "הגרסה אושרה, ונשאר להפיק ממנה את קובץ קורות החיים.",
  submit: "קורות החיים מוכנים, ונשאר לרשום שההגשה בוצעה.",
  download_pdf: "קובץ ה־PDF של קורות החיים מוכן להורדה.",
};

export const actionDescription = (action: string): string | null => actionDescriptions[action] ?? null;

/* Why a control is disabled, as the one short sentence its tooltip carries.

   The server reports only blockers that do not follow from the stage: content that
   failed its check, a review reason that shuts approval, or live work. An action the
   workflow has not reached is not in `blocked_actions` at all. A code with no sentence here disables
   the control without a tooltip rather than showing the reader a `SCREAMING_SNAKE`
   identifier. */
const blockedReasonLabels: Record<string, string> = {
  VALIDATION_FAILED: "הבדיקה נכשלה. צריך לתקן ולבדוק מחדש.",
  PENDING_FACT_REQUIRES_RESOLUTION: "יש טענה בלי עובדה מאושרת מאחוריה.",
  FACT_DELETED_REQUIRES_RESOLUTION: "הטיוטה נשענת על עובדה שנמחקה.",
  DUPLICATE_ACKNOWLEDGEMENT_REQUIRED: "צריך לאשר שזו מועמדות כפולה.",
};

export const blockedReasonLabel = (reason: string): string | null => blockedReasonLabels[reason] ?? null;

/* The title a review reason is shown under, replacing the backend's own `message`
   paragraph.

   The server's sentence stays in the payload - it is still what telemetry and a bug
   report need - but it is not what the screen renders: it is written to be complete
   rather than short, and five of them at once was the wall this map exists to remove.

   Unmapped falls back to a general title rather than to the code, for the same reason
   `blockedReasonLabel` answers null: a `SCREAMING_SNAKE` identifier on screen is a
   missing translation shown to the wrong audience. */
const reasonTitles: Record<string, string> = {
  PENDING_FACT_REQUIRES_RESOLUTION: "טענה בלי עובדה מאושרת",
  FACT_DELETED_REQUIRES_RESOLUTION: "הטיוטה נשענת על עובדה שנמחקה",
  DUPLICATE_ACKNOWLEDGEMENT_REQUIRED: "מועמדות כפולה",
};

export const reasonTitle = (code: string, fallback: string): string => reasonTitles[code] ?? fallback;

/* Warnings carry the same problem and the same answer (§8). None of them disables
   approval; each says what moved and leaves the document as it is. */
const warningTitles: Record<string, string> = {
  NEXT_ACTION_OVERDUE: "הפעולה הבאה באיחור",
  DOCUMENT_ON_OLDER_ANALYSIS: "המסמך בנוי על ניתוח ישן יותר",
  PROFILE_CHANGED: "הפרופיל השתנה מאז שהמסמך נבנה",
  POLICY_CHANGED: "כללי הבחירה השתנו מאז שהמסמך נבנה",
  FACT_SUPERSEDED: "עובדה בטיוטה הוחלפה בגרסה חדשה יותר",
  FACT_KNOWN_INCORRECT: "עובדה בטיוטה סומנה כשגויה",
};

export const warningTitle = (code: string): string => warningTitles[code] ?? "כדאי לשים לב";

const warningDetails: Record<string, string> = {
  DOCUMENT_ON_OLDER_ANALYSIS:
    "קיים ניתוח חדש יותר של המשרה. המסמך נשאר כפי שהוא עד שתבחרו לבנות אותו מחדש מהניתוח החדש - פעולה שמחליפה את בחירת העובדות ומוחקת את תוכן הטיוטה.",
  PROFILE_CHANGED:
    "המסמך נבנה עם גרסה קודמת של הפרופיל. הבדיקה והאישור נעשים מול הפרופיל הנוכחי, כך שהאזהרה אינה מתירה דבר שאינו תקף.",
  POLICY_CHANGED:
    "המסמך נבנה עם גרסה קודמת של כללי הבחירה. הבדיקה והאישור נעשים מול הכללים הנוכחיים, כך שהאזהרה אינה מתירה דבר שאינו תקף.",
};

export const warningDetail = (code: string, fallback: string): string => warningDetails[code] ?? fallback;

/* A face per preparation state, for the same reason the recruitment axis has one: the
   two badges sit side by side in every row, and the icon is what separates "where the CV
   is" from "where the Application is" before the words are read. Exhaustive over the
   generated union. */
export const preparationStateIcons: Record<PreparationState, LucideIcon> = {
  needs_analysis: Clock,
  ready_to_draft: FilePlus2,
  draft_in_progress: FilePen,
  approved: CircleCheck,
  ready: BadgeCheck,
};
