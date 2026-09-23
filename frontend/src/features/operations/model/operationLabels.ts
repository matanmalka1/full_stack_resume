import type { Operation, OperationFailureCode, OperationPhase, OperationStatus, OperationType } from "@/api/contracts";
import { type Tone } from "@/ui/tone";

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

export const statusTones: Record<OperationStatus, Tone> = {
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
const outputTypeLabels: Record<string, string> = {
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
  labels.length <= 1 ? (labels[0] ?? "") : `${labels.slice(0, -1).join(", ")} ו${labels[labels.length - 1]}`;

export const failureTones: Partial<Record<OperationStatus, Tone>> = {
  failed: "blocker",
  cancelled: "neutral",
  interrupted: "warning",
};

export interface FailurePresentation {
  title: string;
  guidance: string;
}

/* Most backend failure details deliberately add no user-facing information beyond the
   translated presentation below. MissingFactRendering and deterministic render failures
   are different: their safe details carry the exact repair the reader needs. Keep the
   parsing narrow so a future or malformed server sentence is not echoed as UI copy. */
export const actionableFailureDetail = (
  code: OperationFailureCode | null | undefined,
  detail: string | null | undefined,
): string | null => {
  if (detail == null) return null;

  if (code === "RENDER_FAILED") {
    const pageCount = /^Rendered PDF has (\d+) pages; maximum (\d+)\.$/.exec(detail);
    if (pageCount !== null) {
      const [, actual, maximum] = pageCount;
      return `קובץ ה־PDF כולל ${actual} עמודים, אך הפרופיל מאפשר לכל היותר ${maximum}. יש לקצר את התוכן לפני יצירה מחדש.`;
    }
    const renderMessages: Record<string, string> = {
      "Rendered PDF text is not sufficiently recoverable by ATS readers.":
        "לא ניתן לחלץ מספיק מהטקסט בקובץ ה־PDF. יש לבדוק את מבנה התוכן לפני יצירה מחדש.",
      "Rendered PDF is missing one or more expected contact links.":
        "בקובץ ה־PDF חסר לפחות קישור קשר צפוי אחד.",
      "Rendered content exceeds the page boundaries.": "חלק מהתוכן חורג מגבולות העמוד.",
      "Rendered document direction does not match its language.": "כיוון המסמך אינו מתאים לשפתו.",
      "Rendered right-to-left content is missing direction isolation.":
        "תוכן מימין לשמאל לא קיבל בידוד כיווניות תקין.",
      "Rendered PDF filename does not match the required recruiter filename.":
        "שם קובץ ה־PDF אינו תואם לשם הנדרש לשליחה.",
      "Rendered HTML is missing or empty.": "קובץ ה־HTML שנוצר חסר או ריק.",
      "Rendered PDF is missing or empty.": "קובץ ה־PDF שנוצר חסר או ריק.",
      "Rendered PDF could not be read.": "לא ניתן לקרוא את קובץ ה־PDF שנוצר.",
      "Rendered output did not pass validation.": "התוצר שנוצר לא עבר את בדיקות התקינות.",
    };
    return renderMessages[detail] ?? null;
  }

  if (code !== "MISSING_FACT_RENDERING") return null;

  const match = /^Fact (\S+) has no '([^']+)' rendering\.$/.exec(detail);
  if (match == null) return null;

  const [, factId, language] = match;
  return `לעובדה ${factId} חסר ניסוח בשפה ${language}.`;
};

const providerRetryGuidance =
  "לא בוצע מעבר אוטומטי למצב דטרמיניסטי. אפשר ליצור ניסיון חדש, או לחזור למועמדות ולבחור באפשרות המשך אחרת כאשר השרת מציע אותה.";
const providerOutputGuidance =
  "התשובה לא הופעלה ולא הוחלפה בשקט בתוצאה דטרמיניסטית. אפשר ליצור ניסיון חדש, או לחזור למועמדות ולבחור באפשרות המשך אחרת כאשר השרת מציע אותה.";

/* Failure codes are decisions a person must be able to distinguish, not technical
   decoration. This map is exhaustive over the generated union: adding a backend code
   fails the build until the screen says what it means and what remains safe. Its
   Hebrew title and guidance replace the backend-authored detail; that detail is used
   only as a forward-compatible fallback for a future code. */
export const failurePresentations: Record<OperationFailureCode, FailurePresentation> = {
  SOURCE_CHANGED: {
    title: "המקור השתנה בזמן הפעולה",
    guidance: "התוצאה לא הופעלה והמצב הקיים נשמר. יש ליצור פעולה חדשה מהאפשרות המוצגת במסך כדי להשתמש במקור העדכני.",
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
  CLAIM_REVIEW_UNCERTAIN: {
    title: "הבדיקה לא הצליחה לקבוע שהניסוח נתמך",
    guidance: "הניסוח לא הופעל והטיוטה הקיימת נשמרה. אפשר לנסות יצירה מחדש או לערוך את השורה.",
  },
  CLAIM_REVIEW_UNSUPPORTED: {
    title: "הבדיקה מצאה טענה שאינה נתמכת בעובדות",
    guidance: "הניסוח לא הופעל והטיוטה הקיימת נשמרה. יש ליצור ניסוח חדש או להסיר את הטענה שאינה נתמכת.",
  },
  SCHEMA_VIOLATION: {
    title: "תשובת הספק לא הייתה במבנה הנדרש",
    guidance: providerOutputGuidance,
  },
  RENDER_FAILED: {
    title: "יצירת קובץ קורות החיים נכשלה",
    guidance: "הגרסה שאושרה נשמרה והתוצר שנכשל לא הופעל. יש לתקן את הסיבה שמופיעה למעלה לפני יצירה מחדש.",
  },
  BROWSER_START_FAILED: {
    title: "מנוע יצירת הקובץ לא התחיל",
    guidance: "הגרסה שאושרה נשמרה. אפשר ליצור ניסיון חדש בלי לשנות אותה.",
  },
  MISSING_FACT_RENDERING: {
    title: "חסר ניסוח בשפת המסמך לעובדה שנבחרה",
    guidance:
      "לא נוצרה טיוטה והמצב הקיים נשמר. ניסיון חוזר מול אותם מקורות ייכשל שוב; יש להשלים ניסוח לעובדה בשפת היעד או להסיר אותה מתוכנית הבחירה.",
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
