import type { ApplicationDetail, PreparationState, WorkingDraftState } from "@/api/contracts";
import {
  BadgeCheck,
  CircleCheck,
  Clock,
  FileCheck2,
  FilePen,
  FilePlus2,
  FileSearch,
  type LucideIcon,
} from "lucide-react";

import type { Tone } from "@/ui/tone";

/* Keyed by the generated unions, so a state added to the §9 projection fails the
   frontend build instead of reaching the screen untranslated. */
export const preparationStateLabels: Record<PreparationState, string> = {
  needs_analysis: "ממתין לניתוח המשרה",
  needs_review: "ממתין להחלטה בסקירה",
  ready_to_draft: "מוכן ליצירת טיוטה",
  draft_in_progress: "טיוטה בעבודה",
  ready_for_approval: "מוכן לאישור",
  approved: "אושר, ממתין ליצירת הקובץ",
  ready: "קורות החיים מוכנים",
};

/* A.2: a state is never colour alone. The tone adds the icon and the Hebrew status word
   the badge already carries. */
export const preparationStateTones: Record<PreparationState, Tone> = {
  needs_analysis: "neutral",
  needs_review: "warning",
  ready_to_draft: "neutral",
  draft_in_progress: "neutral",
  ready_for_approval: "neutral",
  approved: "success",
  ready: "success",
};

export const workingDraftStateLabels: Record<WorkingDraftState, string> = {
  none: "אין טיוטה פעילה",
  editing: "טיוטה בעריכה",
  validation_failed: "האימות נכשל",
  validated: "הטיוטה עברה אימות",
  stale: "הטיוטה אינה מעודכנת מול המקורות",
};

export const workingDraftStateTones: Record<WorkingDraftState, Tone> = {
  none: "neutral",
  editing: "neutral",
  validation_failed: "blocker",
  validated: "success",
  stale: "warning",
};

/* `working_draft_state === "none"` is news only while a draft is expected but absent.
   Before drafting it merely restates the preparation stage; after approval it is the
   normal result of deactivating the draft behind an immutable milestone. */
const preparationStatesImplyingNoDraft = new Set<PreparationState>([
  "needs_analysis",
  "needs_review",
  "ready_to_draft",
  "approved",
  "ready",
]);

export const draftStateIsImplied = (detail: ApplicationDetail): boolean =>
  detail.working_draft_state === "none" && preparationStatesImplyingNoDraft.has(detail.preparation_state);

/* Hebrew names for the actions the projection reports. Deliberately a partial map over
   an open set of strings rather than a Record over an enum this layer invented: the
   action vocabulary is the backend's, `available_actions` mixes preparation commands
   with review-reason resolution actions, and an action with no name here is reported as
   itself rather than guessed at. */
const actionLabels: Record<string, string> = {
  analyze: "ניתוח המשרה",
  apply_analysis_decisions: "החלת החלטות הסקירה",
  create_selection_plan: "בחירת העובדות",
  confirm_and_use_fact: "אישור עובדה ושימוש בה",
  create_draft: "יצירת טיוטה",
  update_working_draft: "עריכת הטיוטה",
  apply_selection_change: "שינוי בחירת העובדות",
  regenerate_section: "יצירה מחדש של פרק",
  regenerate_claim: "יצירה מחדש של טענה",
  archive_working_draft: "העברת הטיוטה לארכיון",
  replace_working_draft: "החלפת הטיוטה",
  validate: "אימות הטיוטה",
  approve: "אישור הגרסה",
  render: "יצירת קובץ קורות החיים",
};

export const actionLabel = (action: string): string => actionLabels[action] ?? action;

/* Why a control is disabled, as the one short sentence its tooltip carries.

   This replaced a disclosure that listed every blocked action with its reasons. Most of
   those rows said only that the workflow had not reached the action yet - true of every
   action downstream of the current stage, and already what the stage badge says - so the
   codes that mean "not there yet" are deliberately absent here: an action the workflow
   has not reached is not offered at all rather than offered and explained.

   What is left is the blocker that does not follow from the stage: a draft that exists
   but failed validation, an approval waiting on a validation run. A code with no sentence
   here disables the control without a tooltip rather than showing the reader a
   `SCREAMING_SNAKE` identifier. */
const blockedReasonLabels: Record<string, string> = {
  VALIDATION_REQUIRED: "צריך להריץ אימות קודם.",
  VALIDATION_FAILED: "האימות נכשל. צריך לתקן ולאמת מחדש.",
  VALIDATION_STALE: "הטיוטה השתנתה מאז האימות.",
  DRAFT_EDITED_AFTER_VALIDATION: "הטיוטה השתנתה מאז האימות.",
  MATERIAL_CLASSIFICATION_AMBIGUITY: "צריך להכריע את סיווג המשרה.",
  ANALYSIS_INCOMPLETE: "הניתוח לא הצליח לקרוא את דרישות המשרה.",
  LOW_FIT_REQUIRES_ACCEPTANCE: "צריך לאשר התאמה נמוכה.",
  HARD_GAP_REQUIRES_DECISION: "צריך להכריע פער חוסם.",
  PENDING_FACT_REQUIRES_RESOLUTION: "יש טענה בלי עובדה מאושרת מאחוריה.",
  KNOWLEDGE_RECONCILIATION_REQUIRED: "צריך להשלים התאמת עובדות.",
  DUPLICATE_ACKNOWLEDGEMENT_REQUIRED: "צריך לאשר שזו מועמדות כפולה.",
};

export const blockedReasonLabel = (reason: string): string | null => blockedReasonLabels[reason] ?? null;

/* The title a review or staleness reason is shown under, replacing the backend's own
   `message` paragraph.

   The server's sentence stays in the payload - it is still what telemetry and a bug
   report need - but it is not what the screen renders: it is written to be complete
   rather than short, and five of them at once was the wall this map exists to remove.

   Unmapped falls back to a general title rather than to the code, for the same reason
   `blockedReasonLabel` answers null: a `SCREAMING_SNAKE` identifier on screen is a
   missing translation shown to the wrong audience. */
const reasonTitles: Record<string, string> = {
  MATERIAL_CLASSIFICATION_AMBIGUITY: "סיווג המשרה לא חד־משמעי",
  ANALYSIS_INCOMPLETE: "הניתוח לא קרא את דרישות המשרה",
  LOW_FIT_REQUIRES_ACCEPTANCE: "ההתאמה למשרה נמוכה",
  HARD_GAP_REQUIRES_DECISION: "יש פער חוסם מול הדרישות",
  PENDING_FACT_REQUIRES_RESOLUTION: "טענה בלי עובדה מאושרת",
  KNOWLEDGE_RECONCILIATION_REQUIRED: "נדרשת התאמת עובדות",
  DUPLICATE_ACKNOWLEDGEMENT_REQUIRED: "מועמדות כפולה",
  FACT_SELECTION_UNRESOLVED: "בחירת העובדות לא הוכרעה",
  JOB_SNAPSHOT_CHANGED: "נוסח המשרה השתנה",
  ANALYSIS_REPLACED: "הניתוח הוחלף",
  SELECTION_PLAN_REPLACED: "בחירת העובדות הוחלפה",
  FACT_CHANGED: "עובדה שמאחורי הטיוטה השתנתה",
  PROFILE_CHANGED: "הפרופיל השתנה",
  POLICY_CHANGED: "כללי הבדיקה השתנו",
  SOURCE_CHANGED: "המקור השתנה",
  DRAFT_EDITED_AFTER_VALIDATION: "הטיוטה השתנתה מאז האימות",
  VALIDATION_STALE: "האימות אינו מעודכן",
};

export const reasonTitle = (code: string, fallback: string): string => reasonTitles[code] ?? fallback;

/* Warnings carry the same problem and the same answer. */
const warningTitles: Record<string, string> = {
  NEXT_ACTION_OVERDUE: "הפעולה הבאה באיחור",
  FACT_SUPERSEDED: "עובדה בטיוטה הוחלפה בגרסה חדשה יותר",
  READY_REVISION_FOR_OLDER_SNAPSHOT: "הגרסה המוכנה שייכת לנוסח משרה ישן",
  READY_REVISION_FOR_OLDER_ANALYSIS: "הגרסה המוכנה שייכת לניתוח ישן",
};

export const warningTitle = (code: string): string => warningTitles[code] ?? "כדאי לשים לב";

const warningDetails: Record<string, string> = {
  READY_REVISION_FOR_OLDER_SNAPSHOT:
    "הגרסה המוכנה שייכת לתצלום משרה ישן יותר מהתצלום הפעיל. הקבצים שלה נשארים תקינים וזמינים להורדה.",
  READY_REVISION_FOR_OLDER_ANALYSIS:
    "הגרסה המוכנה שייכת לניתוח ישן יותר מהניתוח הפעיל. הקבצים שלה נשארים תקינים וזמינים להורדה.",
};

export const warningDetail = (code: string, fallback: string): string => warningDetails[code] ?? fallback;

/* A face per preparation state, for the same reason the recruitment axis has one: the
   two badges sit side by side in every row, and the icon is what separates "where the CV
   is" from "where the Application is" before the words are read. Exhaustive over the
   generated union. */
export const preparationStateIcons: Record<PreparationState, LucideIcon> = {
  needs_analysis: Clock,
  needs_review: FileSearch,
  ready_to_draft: FilePlus2,
  draft_in_progress: FilePen,
  ready_for_approval: FileCheck2,
  approved: CircleCheck,
  ready: BadgeCheck,
};
