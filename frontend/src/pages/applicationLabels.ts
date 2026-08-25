import type { PreparationState, WorkingDraftState } from "../api/contracts";
import type { StatusTone } from "../ui/status";

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
export const preparationStateTones: Record<PreparationState, StatusTone> = {
  needs_analysis: "neutral",
  needs_review: "warning",
  ready_to_draft: "neutral",
  draft_in_progress: "neutral",
  ready_for_approval: "neutral",
  approved: "success",
  ready: "success",
};

/* What the stage means for the reader, in one sentence, keyed by the same generated
   union as the labels above.

   This is the sentence the screen used to make them open a disclosure and read fourteen
   rows of blocked actions to infer. It says what the workflow is waiting on and what
   comes after it - not what is unavailable, which is the whole rest of the workflow and
   says nothing. It decides nothing (A.1): the offered controls stay the projection's. */
export const preparationStateNextStep: Record<PreparationState, string> = {
  needs_analysis:
    "ניתוח המשרה קורא את תצלום המשרה ומסיק מה נדרש בה. אחריו ייפתחו בחירת העובדות ויצירת הטיוטה.",
  needs_review:
    "הניתוח מוכן והוא ממתין להחלטה שלך. אחרי החלטות הסקירה אפשר יהיה ליצור טיוטה.",
  ready_to_draft:
    "הניתוח ותוכנית הבחירה מוכנים. יצירת הטיוטה מרכיבה מהם קורות חיים לעריכה.",
  draft_in_progress:
    "יש טיוטה פעילה לעבוד עליה. כשהיא מוכנה, אימות בודק אותה מול העובדות הקנוניות.",
  ready_for_approval:
    "הטיוטה עברה אימות. אישור הגרסה יוצר רשומה קבועה שאינה משתנה עוד.",
  approved:
    "הגרסה אושרה ונשמרה כפי שהיא. נותר ליצור ממנה את קובץ קורות החיים.",
  ready: "קורות החיים מוכנים. אפשר לצפות בגרסה המוכנה ולהגיש אותה.",
};

export const workingDraftStateLabels: Record<WorkingDraftState, string> = {
  none: "אין טיוטה פעילה",
  editing: "טיוטה בעריכה",
  validation_failed: "האימות נכשל",
  validated: "הטיוטה עברה אימות",
  stale: "הטיוטה אינה מעודכנת מול המקורות",
};

export const workingDraftStateTones: Record<WorkingDraftState, StatusTone> = {
  none: "neutral",
  editing: "neutral",
  validation_failed: "blocker",
  validated: "success",
  stale: "warning",
};

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

/* Hebrew reasons for a blocked action, in the same partial-map shape and for the same
   reason as `actionLabels`: `BlockedActionResponse.reasons` is `list[str]`, and it
   carries review and staleness codes alongside the action-policy ones. A code with no
   name here is reported as itself rather than guessed at, so an unnamed reason reads as
   a missing translation instead of a wrong explanation.

   These sentences say what is missing, not what the code is called. The disclosure they
   sit in is what the F gate means by explaining a blocker without requiring the reader
   to know an identifier. */
const blockedReasonLabels: Record<string, string> = {
  NO_REVIEW_DECISION_REQUIRED: "אין החלטת סקירה שממתינה להכרעה.",
  ANALYSIS_OR_SELECTION_PLAN_REQUIRED: "נדרשים ניתוח משרה ותוכנית בחירת עובדות פעילים.",
  WORKING_DRAFT_REQUIRED: "אין טיוטה פעילה לעבוד עליה.",
  VALIDATED_DRAFT_REQUIRED: "נדרשת טיוטה שעברה אימות.",
  VALIDATION_REQUIRED: "יש להריץ אימות על הטיוטה לפני האישור.",
  VALIDATION_FAILED: "האימות נכשל. יש לתקן את החסימות ולאמת מחדש.",
  APPROVED_REVISION_REQUIRED: "נדרשת גרסה מאושרת.",
  ACTION_NOT_AVAILABLE: "הפעולה אינה זמינה במצב הנוכחי.",
};

export const blockedReasonLabel = (reason: string): string =>
  blockedReasonLabels[reason] ?? reason;
