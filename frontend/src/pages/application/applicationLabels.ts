import type {
  ApplicationDetail,
  ApplicationPreset,
  PreparationState,
  RecruitmentStatus,
  WorkingDraftState,
} from "../../api/contracts";
import {
  Archive,
  BadgeCheck,
  CircleCheck,
  CircleSlash,
  CircleX,
  ClipboardList,
  Clock,
  FileCheck2,
  FilePen,
  FilePlus2,
  FileSearch,
  PhoneCall,
  Send,
  Trophy,
  UserRound,
} from "lucide-react";
import type { LucideIcon } from "lucide-react";

import type { StatusTone } from "../../ui/status";

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
  LOW_FIT_REQUIRES_ACCEPTANCE: "צריך לאשר התאמה נמוכה.",
  HARD_GAP_REQUIRES_DECISION: "צריך להכריע פער חוסם.",
  PENDING_FACT_REQUIRES_RESOLUTION: "יש טענה בלי עובדה מאושרת מאחוריה.",
  KNOWLEDGE_RECONCILIATION_REQUIRED: "צריך להשלים התאמת עובדות.",
  DUPLICATE_ACKNOWLEDGEMENT_REQUIRED: "צריך לאשר שזו מועמדות כפולה.",
};

/* The recruitment axis, which is where the Application stands with the employer - as
   opposed to `preparation_state`, which is how far the CV for it has got. The two are
   independent and the dashboard shows both, so they need separate vocabularies.

   An open string map rather than a Record over a union: `recruitment_status` is `str` at
   the HTTP boundary, and a status this build does not know is shown as its raw value
   rather than hidden. */
export const recruitmentStatusLabels: Record<RecruitmentStatus, string> = {
  saved: "נשמר",
  applied: "הוגש",
  recruiter_screen: "שיחת מגייס",
  interview: "ראיון",
  assignment: "משימה",
  final_stage: "שלב סופי",
  offer: "הצעה",
  accepted: "התקבל",
  rejected: "נדחה",
  withdrawn: "בוטל",
  closed: "סגור",
};

export const recruitmentStatusLabel = (status: string): string =>
  status in recruitmentStatusLabels ? recruitmentStatusLabels[status as RecruitmentStatus] : status;

const blockedReasonLabel = (reason: string): string | null => blockedReasonLabels[reason] ?? null;

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

/* The board's named questions, in the order the chips offer them. Keyed by the generated
   union, so a preset added to the application layer fails the build here instead of
   reaching the chip row untranslated.

   Each chip is one value of the `preset` parameter, not a filter this client assembles:
   the predicates are the projection's, and the chip only names them. */
export const applicationPresetLabels: Record<ApplicationPreset, string> = {
  needs_attention: "דורש טיפול",
  ready_to_send: "מסמכים מוכנים לשליחה",
  active_interviews: "ראיונות פעילים",
};

/* The recruitment stages the chips and the stage filter name, in the workflow order the
   domain declares them rather than alphabetically. */
export const recruitmentStatusOrder: readonly RecruitmentStatus[] = [
  "saved",
  "applied",
  "recruiter_screen",
  "interview",
  "assignment",
  "final_stage",
  "offer",
  "accepted",
  "rejected",
  "withdrawn",
  "closed",
];

/* The recruitment axis as the board draws it: a colour and an icon per status.

   `preparation_state` already has tones, and this is the axis beside it - a row shows
   both, so the two need to be distinguishable at a glance rather than reading as one
   long line of identical grey pills. The colour is never the signal on its own: every
   badge carries the Hebrew status word, and the icon repeats what the word says.

   Keyed by the generated union, so a status added to the domain fails the build here
   instead of arriving without a face. */
const recruitmentStatusTones: Record<RecruitmentStatus, StatusTone> = {
  saved: "neutral",
  applied: "progress",
  recruiter_screen: "progress",
  interview: "progress",
  assignment: "progress",
  final_stage: "warning",
  offer: "success",
  accepted: "success",
  rejected: "blocker",
  withdrawn: "neutral",
  closed: "neutral",
};

const recruitmentStatusIcons: Record<RecruitmentStatus, LucideIcon> = {
  saved: Clock,
  applied: Send,
  recruiter_screen: PhoneCall,
  interview: UserRound,
  assignment: ClipboardList,
  final_stage: Trophy,
  offer: BadgeCheck,
  accepted: CircleCheck,
  rejected: CircleX,
  withdrawn: CircleSlash,
  closed: Archive,
};

/* Both looked up through the same open-string door `recruitmentStatusLabel` uses:
   `recruitment_status` is `str` at the HTTP boundary, so a status this build does not
   know gets the neutral tone and a plain clock rather than crashing the row or being
   hidden from it. */
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

export const recruitmentStatusTone = (status: string): StatusTone =>
  status in recruitmentStatusTones ? recruitmentStatusTones[status as RecruitmentStatus] : "neutral";

export const recruitmentStatusIcon = (status: string): LucideIcon =>
  status in recruitmentStatusIcons ? recruitmentStatusIcons[status as RecruitmentStatus] : Clock;
