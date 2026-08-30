import type {
  Operation,
  OperationFailureCode,
  OperationPhase,
  OperationStatus,
  OperationType,
} from "../api/contracts";
import { type StatusTone } from "../ui/status";

/* The Hebrew vocabulary of an Operation, in one module because two surfaces speak it: the
   Operation screen, which a direct link still reaches, and the panel on the Application
   screen, where work queued from that screen is now watched without leaving it.

   They have to say the same thing about the same Operation - a status, a phase, and a
   failure are not worth two translations that can drift - so the maps live here and the
   two screens differ only in how much of the record they lay out. */
/* Keyed by the generated unions, so a status or phase added to the backend lifecycle
   fails the frontend build instead of reaching the screen untranslated. */
export const statusLabels: Record<OperationStatus, string> = {
  queued: "ממתינה בתור",
  running: "מתבצעת",
  succeeded: "הושלמה",
  failed: "נכשלה",
  cancelled: "בוטלה",
  interrupted: "נקטעה",
};

/* What the operation is, which the status alone never says. Keyed by the generated
   union, so a new backend operation type fails the build rather than reaching the
   heading untranslated. */
export const operationTypeLabels: Record<OperationType, string> = {
  analyze_job: "ניתוח המשרה",
  propose_selection_plan: "בחירת העובדות",
  create_draft: "יצירת הטיוטה",
  regenerate_section: "יצירה מחדש של פרק",
  regenerate_claim: "יצירה מחדש של טענה",
  render_revision: "יצירת קובץ קורות החיים",
};

export const statusTones: Record<OperationStatus, StatusTone> = {
  queued: "progress",
  running: "progress",
  succeeded: "success",
  failed: "blocker",
  cancelled: "neutral",
  interrupted: "warning",
};

export const phaseLabels: Record<OperationPhase, string> = {
  queued: "ממתינה בתור",
  waiting_for_application: "ממתינה למועמדות",
  waiting_for_render_slot: "ממתינה לתור הרינדור",
  waiting_for_ai_slot: "ממתינה לתור המודל",
  pre_execution_check: "בדיקה לפני ביצוע",
  executing: "בביצוע",
  retry_wait: "המתנה לפני ניסיון חוזר",
  pre_activation_check: "בדיקה לפני הפעלת התוצר",
  activating: "מפעילה את התוצר",
  completed: "הושלמה",
};

/* What an operation produced, named for the reader. Deliberately a partial map over an
   open string rather than a Record over an enum: `output_type` is `str` in the schema, so
   a type this map does not know is skipped rather than printed raw - an internal token in
   a success line teaches nothing and looks like a leak.

   `provider_response` is deliberately absent. It is registered as an output, but it is
   the provider's own text, and this screen states elsewhere that it shows no provider
   text. It stays in the record and out of the result line. */
export const outputTypeLabels: Record<string, string> = {
  job_analysis: "ניתוח המשרה",
  selection_plan: "תוכנית בחירת העובדות",
  working_draft: "טיוטה",
};

/* §11 separates existence from activation: a failed or cancelled Operation can own an
   output that was recorded as inactive evidence. Only the active ones are results, so
   only they are named - an inactive output reported as something the operation produced
   would claim the state changed when it did not. */
export const activeOutputLabels = (operation: Operation): string[] =>
  operation.outputs
    .filter((output) => output.active)
    .map((output) => outputTypeLabels[output.output_type])
    .filter((label): label is string => label !== undefined);

/* Hebrew joins a list by prefixing the last item with "ו", not by placing a separator
   between the last two - so this is a prefix on the final label rather than a join
   string, and a one-item list has no conjunction at all. */
export const joinHebrewList = (labels: string[]): string =>
  labels.length <= 1
    ? (labels[0] ?? "")
    : `${labels.slice(0, -1).join(", ")} ו${labels[labels.length - 1]}`;

export const failureTones: Partial<Record<OperationStatus, StatusTone>> = {
  failed: "blocker",
  cancelled: "neutral",
  interrupted: "warning",
};

export interface FailurePresentation {
  title: string;
  guidance: string;
}

const providerRetryGuidance =
  "לא בוצע מעבר אוטומטי למצב דטרמיניסטי. אפשר ליצור ניסיון חדש, או לחזור למועמדות ולבחור באפשרות המשך אחרת כאשר השרת מציע אותה.";
const providerOutputGuidance =
  "התשובה לא הופעלה ולא הוחלפה בשקט בתוצאה דטרמיניסטית. אפשר ליצור ניסיון חדש, או לחזור למועמדות ולבחור באפשרות המשך אחרת כאשר השרת מציע אותה.";

/* Failure codes are decisions a person must be able to distinguish, not technical
   decoration. This map is exhaustive over the generated union: adding a backend code
   fails the build until the screen says what it means and what remains safe. The
   backend-authored safe detail is still shown verbatim; this copy explains the next
   choice without exposing logs, paths, or provider text. */
export const failurePresentations: Record<OperationFailureCode, FailurePresentation> = {
  SOURCE_CHANGED: {
    title: "המקור השתנה בזמן הפעולה",
    guidance:
      "התוצאה לא הופעלה והמצב הקיים נשמר. ניסיון חוזר משתמש שוב במקורות שהוקפאו לפעולה הזו ועלול להיכשל מאותה סיבה; חזרה למועמדות מציגה את הפעולות שמותר לבצע מול המקור העדכני.",
  },
  PROVIDER_TIMEOUT: {
    title: "ספק הבינה המלאכותית לא השיב בזמן",
    guidance: providerRetryGuidance,
  },
  PROVIDER_RATE_LIMITED: {
    title: "ספק הבינה המלאכותית הגביל את הבקשה",
    guidance: providerRetryGuidance,
  },
  PROVIDER_UNAVAILABLE: {
    title: "ספק הבינה המלאכותית אינו זמין",
    guidance: providerRetryGuidance,
  },
  PROVIDER_REFUSED: {
    title: "ספק הבינה המלאכותית סירב לבקשה",
    guidance: providerRetryGuidance,
  },
  INVALID_OUTPUT: {
    title: "הצעת הספק לא הייתה בטוחה לשימוש",
    guidance: providerOutputGuidance,
  },
  SCHEMA_VIOLATION: {
    title: "תשובת הספק לא הייתה במבנה הנדרש",
    guidance: providerOutputGuidance,
  },
  RENDER_FAILED: {
    title: "יצירת קובץ קורות החיים נכשלה",
    guidance: "הגרסה שאושרה נשמרה. אפשר ליצור ניסיון חדש בלי לשנות אותה.",
  },
  BROWSER_START_FAILED: {
    title: "מנוע יצירת הקובץ לא התחיל",
    guidance: "הגרסה שאושרה נשמרה. אפשר ליצור ניסיון חדש בלי לשנות אותה.",
  },
  VALIDATION_EXECUTION_FAILED: {
    title: "לא ניתן להשלים את בדיקות הפעולה",
    guidance: "המצב שהיה פעיל לפני הפעולה נשמר. אפשר ליצור ניסיון חדש או לחזור למועמדות.",
  },
  CANCELLED_BEFORE_ACTIVATION: {
    title: "הפעולה בוטלה לפני הפעלת התוצאה",
    guidance: "תוצאה שהושלמה לאחר בקשת הביטול נשמרת כראיה לא פעילה ואינה מחליפה את המצב הקיים.",
  },
};

