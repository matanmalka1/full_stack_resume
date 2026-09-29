import type { ProblemDetails } from "@/api/client";

/* One catalogue for every failure the API can report, so the same refusal reads the same
   on every screen. A message has two parts, and the owning screen supplies the third:

   - the title is the screen's own - what did not happen ("ההגדרות לא נשמרו");
   - `reason` says why, in one short sentence;
   - `action` says what the reader can do now.

   The server's `title` and `detail` are never shown. They are English, written for a
   log, and may name internal records; `reportError` keeps them in the console. A code
   this table does not know falls back to the screen's own contextual detail. */
interface ProblemMessage {
  action: string;
  reason: string;
}

const retryLater = "אפשר לנסות שוב בעוד כמה דקות.";
const refreshAndRetry = "אפשר לרענן את העמוד ולנסות שוב.";
const fixFields = "יש לתקן את השדות המסומנים ולנסות שוב.";
const providerFailure: ProblemMessage = {
  reason: "ספק ה־AI לא החזיר תשובה שאפשר להשתמש בה. שום דבר לא השתנה.",
  action: "אפשר לנסות שוב.",
};
const artifactUnavailable: ProblemMessage = {
  reason: "הקובץ השמור חסר או שתוכנו אינו תואם לרשומה.",
  action: "אפשר להריץ בדיקת תקינות במסך העובדות.",
};

const problemMessages: Record<string, ProblemMessage> = {
  UNKNOWN_RECORD: { reason: "הפריט המבוקש לא נמצא. ייתכן שנמחק.", action: refreshAndRetry },
  ROUTE_NOT_FOUND: { reason: "הכתובת המבוקשת אינה קיימת.", action: "אפשר לחזור ללוח המועמדויות." },
  REQUEST_VALIDATION_FAILED: { reason: "חלק מהפרטים אינם תקינים.", action: fixFields },
  APPLICATION_INTAKE_INVALID: { reason: "חלק מהפרטים אינם תקינים.", action: fixFields },
  BAD_REQUEST: { reason: "הבקשה לא התקבלה.", action: refreshAndRetry },
  INVALID_CONTENT_LENGTH: { reason: "הבקשה לא התקבלה.", action: refreshAndRetry },
  STATE_CONFLICT: { reason: "הנתונים השתנו מאז שהעמוד נטען.", action: refreshAndRetry },
  IDEMPOTENCY_KEY_REUSED: { reason: "הבקשה כבר נשלחה עם תוכן אחר.", action: refreshAndRetry },
  DOCUMENT_CHANGED: {
    reason: "המסמך עודכן מאז שנפתח.",
    action: "יש לרענן את העמוד, לבדוק את הגרסה העדכנית ולנסות שוב.",
  },
  SOURCE_CHANGED: { reason: "המקור השתנה בזמן הפעולה, והתוצאה לא הופעלה.", action: refreshAndRetry },
  PRECONDITION_FAILED: { reason: "הפעולה אינה זמינה בשלב הנוכחי.", action: "יש להשלים את השלבים הקודמים ולנסות שוב." },
  LINEAGE_BROKEN: { reason: "מקורות המסמך אינם תואמים זה לזה.", action: "יש לחזור למועמדות ולהמשיך מהמצב העדכני." },
  VALIDATION_BLOCKED: { reason: "הבדיקה מצאה בעיות שחוסמות את הפעולה.", action: "יש לתקן אותן ולנסות שוב." },
  VALIDATION_FAILED: { reason: "הבדיקה מצאה בעיות שחוסמות את הפעולה.", action: "יש לתקן אותן ולנסות שוב." },
  DOCUMENT_NOT_APPROVED: { reason: "המסמך עדיין לא אושר.", action: "יש לאשר את הגרסה הנוכחית לפני יצירת הקבצים." },
  DOCUMENT_NOT_READY: {
    reason: "המסמך השתנה מאז שהקבצים נוצרו.",
    action: "יש לאשר את המסמך וליצור את הקבצים מחדש.",
  },
  REGENERATION_REQUIRED: {
    reason: "המסמך כולל ניסוח ידני שבנייה מחדש הייתה מוחקת, ולכן הבחירה לא השתנתה.",
    action: "אפשר לשנות אותה ביצירה מחדש של הפרק או של השורה.",
  },
  MISSING_FACT_RENDERING: {
    reason: "לאחת העובדות שנבחרו אין ניסוח בשפת המסמך.",
    action: "יש להוסיף לה ניסוח או להסיר אותה מהבחירה.",
  },
  KNOWLEDGE_REJECTED: { reason: "השינוי בעובדה נדחה, והעובדה לא השתנתה.", action: "יש לבדוק את הפרטים ולנסות שוב." },
  KNOWLEDGE_RECONCILIATION_REQUIRED: {
    reason: "מאגר העובדות אינו תואם ליומן השינויים שלו.",
    action: "יש להשלים את התאמת מאגר העובדות לפני שממשיכים.",
  },
  DUPLICATE_ACKNOWLEDGEMENT_REQUIRED: {
    reason: "נמצאה מועמדות דומה.",
    action: "יש לבדוק את ההתאמות ולאשר אם ליצור מועמדות נוספת.",
  },
  PROPOSAL_REJECTED: { reason: "ההצעה לא עברה את הבדיקה, והמצב הקיים נשמר.", action: "אפשר לנסות שוב." },
  CLAIM_REVIEW_UNCERTAIN: {
    reason: "הבדיקה לא הצליחה לקבוע שהניסוח נתמך בעובדות.",
    action: "אפשר לנסות שוב או לערוך את השורה.",
  },
  CLAIM_REVIEW_UNSUPPORTED: {
    reason: "הניסוח כולל טענה שאינה נתמכת בעובדות.",
    action: "יש לערוך את השורה או להסיר אותה.",
  },
  ARTIFACT_CONTAINMENT_REFUSED: artifactUnavailable,
  ARTIFACT_PAYLOAD_MISSING: artifactUnavailable,
  ARTIFACT_HASH_MISMATCH: artifactUnavailable,
  PROVIDER_NOT_CONFIGURED: {
    reason: "לא הוגדר ספק AI, ולכן הבקשה לא נשלחה.",
    action: "יש להגדיר ספק AI ולנסות שוב.",
  },
  PROVIDER_TIMEOUT: providerFailure,
  PROVIDER_RATE_LIMITED: providerFailure,
  PROVIDER_UNAVAILABLE: providerFailure,
  PROVIDER_REFUSED: providerFailure,
  PROVIDER_SCHEMA_VIOLATION: providerFailure,
  PROVIDER_INVALID_OUTPUT: providerFailure,
  DEPENDENCY_UNAVAILABLE: { reason: "שירות שהמערכת נשענת עליו אינו זמין כרגע.", action: retryLater },
  SERVICE_UNAVAILABLE: { reason: "השרת אינו זמין כרגע.", action: retryLater },
  INFRASTRUCTURE_FAILURE: { reason: "אירעה תקלה בשרת. המידע הקיים לא השתנה.", action: "אפשר לנסות שוב." },
  INTERNAL_ERROR: { reason: "אירעה תקלה בשרת. המידע הקיים לא השתנה.", action: "אפשר לנסות שוב." },
  NETWORK_UNAVAILABLE: { reason: "אין חיבור לשרת.", action: "יש לוודא שהשרת פועל ולנסות שוב." },
  INVALID_SERVER_RESPONSE: { reason: "התקבלה מהשרת תשובה לא צפויה.", action: refreshAndRetry },
  UNEXPECTED_HTTP_ERROR: { reason: "הבקשה לא הושלמה.", action: refreshAndRetry },
  METHOD_NOT_ALLOWED: { reason: "הפעולה אינה זמינה בגרסה הזו של השרת.", action: refreshAndRetry },
  BODY_LIMIT_EXCEEDED: { reason: "התוכן שנשלח ארוך מדי.", action: "יש לקצר אותו ולנסות שוב." },
  PAYLOAD_TOO_LARGE: { reason: "התוכן שנשלח ארוך מדי.", action: "יש לקצר אותו ולנסות שוב." },
  ORIGIN_NOT_ALLOWED: { reason: "הגישה נדחתה.", action: "יש לפתוח את המערכת מהכתובת שהוגדרה עבורה." },
  FORBIDDEN: { reason: "הגישה נדחתה.", action: "יש לפתוח את המערכת מהכתובת שהוגדרה עבורה." },
};

/* The known reason and action for a problem code, or null for a code this client does
   not know - the caller then uses its own contextual copy, never the server's prose. */
export const problemMessage = (problem: ProblemDetails): ProblemMessage | null => problemMessages[problem.code] ?? null;

/** The ProblemDetails an API failure carries, or null for anything else (a local error). */
export const problemDetailsFrom = (error: unknown): ProblemDetails | null => {
  if (typeof error !== "object" || error === null || !("problem" in error)) {
    return null;
  }

  const problem = error.problem;
  if (
    typeof problem !== "object" ||
    problem === null ||
    !("title" in problem) ||
    !("detail" in problem) ||
    !("code" in problem) ||
    !("type" in problem) ||
    !("status" in problem)
  ) {
    return null;
  }

  return typeof problem.title === "string" &&
    typeof problem.detail === "string" &&
    typeof problem.code === "string" &&
    typeof problem.type === "string" &&
    typeof problem.status === "number"
    ? (problem as ProblemDetails)
    : null;
};

/** One sentence for places too small for a callout - a status line, a toast-sized
    notice. The known reason and action, or the caller's fallback. */
export const problemSentence = (error: unknown, fallback: string): string => {
  const problem = problemDetailsFrom(error);
  const message = problem === null ? null : problemMessage(problem);
  return message === null ? fallback : `${message.reason} ${message.action}`;
};

const fieldLabels: Record<string, string> = {
  company: "חברה",
  role_title: "תפקיד",
  target_role: "תפקיד היעד",
  source_url: "כתובת המשרה",
  job_text: "טקסט המשרה",
  target_status: "שלב בתהליך",
  reason: "סיבת השינוי",
  next_action: "הפעולה הבאה",
  next_action_date: "תאריך יעד",
  notes: "הערות",
  source: "מקור",
  meaning: "משמעות העובדה",
  renderings: "ניסוח העובדה",
  english: "ניסוח באנגלית",
  tags: "תגיות",
  provenance: "מקור המידע",
  resume_style: "סגנון קורות החיים",
  submitted_at: "מועד ההגשה",
};

/* Short, and about the value rather than the request: the field's own label already says
   which value. Pydantic's issue types name the rule the value broke. */
const fieldIssueMessage = (type: unknown): string => {
  if (typeof type !== "string") return "הערך אינו תקין.";
  if (type === "missing" || type === "string_too_short") return "יש למלא את השדה.";
  if (type === "string_too_long" || type === "too_long") return "הערך ארוך מדי.";
  if (type.startsWith("url")) return "הכתובת אינה תקינה.";
  if (type.startsWith("datetime") || type.startsWith("date")) return "התאריך אינו תקין.";
  return "הערך אינו תקין.";
};

/** Server-side field refusals, keyed by the API's field name, each with a short message
    meant to sit under that field. The last named part of an issue's location is the
    field; `APPLICATION_INTAKE_INVALID` names its field directly. */
export const problemFieldErrors = (error: unknown): Map<string, string> => {
  const fields = new Map<string, string>();
  const problem = problemDetailsFrom(error);
  if (problem === null) return fields;

  const namedField = problem.context?.field;
  if (problem.code === "APPLICATION_INTAKE_INVALID" && typeof namedField === "string") {
    fields.set(namedField, "הערך אינו תקין.");
    return fields;
  }

  const issues = problem.context?.issues;
  if (problem.code !== "REQUEST_VALIDATION_FAILED" || !Array.isArray(issues)) return fields;

  for (const issue of issues) {
    if (typeof issue !== "object" || issue === null || !("location" in issue) || !Array.isArray(issue.location)) {
      continue;
    }
    const field = issue.location
      .toReversed()
      .find((part: unknown): part is string => typeof part === "string" && part !== "body");
    if (field !== undefined && !fields.has(field)) {
      fields.set(field, fieldIssueMessage("type" in issue ? issue.type : undefined));
    }
  }
  return fields;
};

/** A field refusal the screen could not place under its own control, as one list line. */
export const fieldIssueLine = (field: string, message: string): string =>
  `${fieldLabels[field] ?? "אחד השדות"}: ${message}`;

const validationIssueMessages: Record<string, string> = {
  "draft-manifest-mismatch": "תוכן הטיוטה אינו תואם לגרסה שנשמרה. יש לשמור מחדש ולנסות שוב.",
  "misplaced-headline-claim": "כותרת המסמך נמצאת במקום שאינו מתאים.",
  "duplicate-claim-id": "אותה טענה מופיעה יותר מפעם אחת.",
  "claim-hash-mismatch": "תוכן הטענה השתנה ללא שמירה תקינה.",
  "unlinked-claim": "טענה אינה מקושרת לעובדה מאושרת.",
  "unsupported-derived-claim": "הניסוח שנגזר אינו נתמך באופן מלא בעובדה המקושרת.",
  "pending-claim": "טענה מבוססת על עובדה שעדיין ממתינה לאישור.",
  "canonical-claim-cardinality": "טענה קנונית חייבת להיות מקושרת לעובדה מאושרת אחת בלבד.",
  "invalid-composite-claim": "לא ניתן להרכיב את הטענה מהעובדות שנבחרו.",
  "composite-wording-mismatch": "ניסוח הטענה המשולבת אינו תואם לתבנית המאושרת.",
  "invalid-fact-link": "אחד מקישורי העובדות אינו תקין.",
  "canonical-wording-mismatch": "ניסוח הטענה אינו תואם לניסוח המאושר של העובדה.",
  "canonical-style-mismatch": "סגנון הטענה אינו תואם לסגנון המאושר של העובדה.",
  "fact-store-version-mismatch": "הטיוטה נבנתה מגרסה קודמת של מאגר העובדות.",
  "profile-mismatch": "הטיוטה אינה תואמת לפרופיל שנבחר.",
  "emphasis-not-allowed": "הדגש שנבחר אינו זמין בפרופיל הזה.",
  "low-fit": "נדרש אישור מפורש כדי להמשיך עם התאמה נמוכה.",
  "hard-gap-not-accepted": "יש להכריע בפערים מול דרישות החובה של המשרה.",
  "incomplete-analysis-not-accepted": "יש לאשר במפורש המשך עם ניתוח חלקי.",
  "section-order": "סדר הפרקים אינו תואם לפרופיל שנבחר.",
  "fact-outside-profile-section": "עובדה מקושרת לפרק שאינו מתאים לה.",
  "section-budget-exceeded": "אחד הפרקים כולל יותר מדי טענות.",
  "pinned-fact-dropped": "עובדה שחייבת להופיע חסרה מהטיוטה.",
  "role-block-empty": "כותרת תפקיד מופיעה ללא תוכן מתחתיה.",
  "required-tag-uncovered": "הטיוטה אינה מכסה נושא חובה בפרופיל.",
  "emphasis-coverage-low": "הטיוטה מכסה מעט מדי מהנושאים המועדפים לדגש שנבחר.",
  "selected-fact-set-mismatch": "רשימת העובדות שנבחרו אינה תואמת לטענות בטיוטה.",
  "historical-title-placement": "שמות תפקידים קודמים חייבים להישאר ככותרות מדויקות.",
  "unsafe-headline": "כותרת קורות החיים אינה נתמכת בפרופיל המאושר.",
  "stale-team-size": "הטיוטה כוללת נתון ישן על גודל הצוות.",
  "stale-annual-growth": "הטיוטה כוללת נתון צמיחה שאינו עדכני.",
  "unsupported-saas-sales": "הטיוטה מייחסת ניסיון במכירת תוכנה ללא עובדה תומכת.",
  "html-missing": "קובץ התצוגה של קורות החיים חסר.",
  "pdf-missing": "קובץ קורות החיים חסר.",
  "pdf-corrupt": "לא ניתן לקרוא את קובץ קורות החיים.",
  "page-count": "מספר העמודים אינו מתאים לפרופיל שנבחר.",
  "text-coverage": "חלק מתוכן קורות החיים חסר בקובץ שנוצר.",
  "link-targets": "אחד הקישורים בקובץ אינו תואם לפרטי הקשר.",
  overflow: "חלק מהתוכן חורג מגבולות העמוד.",
  "document-direction": "כיוון המסמך אינו תואם לשפה שנבחרה.",
  "mixed-direction-isolation": "טקסט משולב בעברית ובאנגלית לא הוצג בכיוון תקין.",
  filename: "שם הקובץ אינו תואם לתפקיד ולפרטי המועמד.",
  "revision-application-mismatch": "הגרסה המאושרת אינה שייכת למועמדות הזו.",
  "manifest-application-mismatch": "קובץ מבנה הטיוטה אינו שייך למועמדות הזו.",
  "markdown-application-mismatch": "תוכן הטיוטה המאושר אינו שייך למועמדות הזו.",
  "manifest-unreadable": "לא ניתן לקרוא את מבנה הטיוטה המאושר.",
  "no-approval-validation": "לא נמצא אימות שעבר עבור הגרסה המאושרת.",
  "approval-validation-failed": "האימות של הגרסה המאושרת נכשל.",
  "no-rendered-pdf": "לא נמצא קובץ קורות חיים שנוצר מהגרסה המאושרת.",
  "no-post-render-validation": "לא נמצאה בדיקה לקובץ קורות החיים שנוצר.",
  "post-render-validation-failed": "בדיקת קובץ קורות החיים שנוצר נכשלה.",
  "no-decision-record": "חסר תיעוד ההחלטות של הגרסה המאושרת.",
  "unknown-job-analysis": "ניתוח המשרה של הגרסה המאושרת אינו זמין.",
  "unknown-selection-plan": "תוכנית בחירת העובדות של הגרסה המאושרת אינה זמינה.",
  "analysis-application-mismatch": "ניתוח המשרה אינו שייך למועמדות הזו.",
  "analysis-snapshot-mismatch": "ניתוח המשרה אינו תואם לגרסת המשרה שנשמרה.",
  "plan-analysis-mismatch": "תוכנית בחירת העובדות אינה תואמת לניתוח המשרה.",
  "plan-application-mismatch": "תוכנית בחירת העובדות אינה שייכת למועמדות הזו.",
};

export const localizedValidationIssue = (code: string, fallback: string): string =>
  validationIssueMessages[code] ?? fallback;
