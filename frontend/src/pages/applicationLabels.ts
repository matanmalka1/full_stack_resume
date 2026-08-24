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
