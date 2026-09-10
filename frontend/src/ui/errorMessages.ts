import type { ProblemDetails } from "@/api/client";

interface ErrorMessage {
  detail: string;
  title: string;
}

const problemMessages: Record<string, ErrorMessage> = {
  UNKNOWN_RECORD: { title: "הרשומה לא נמצאה", detail: "הפריט המבוקש אינו קיים או שכבר אינו זמין." },
  ROUTE_NOT_FOUND: { title: "העמוד לא נמצא", detail: "הכתובת המבוקשת אינה קיימת." },
  REQUEST_VALIDATION_FAILED: { title: "יש לתקן את הפרטים", detail: "חלק מהשדות אינם תקינים. יש לתקן אותם ולנסות שוב." },
  STATE_CONFLICT: { title: "המידע השתנה", detail: "הפעולה מתנגשת במצב העדכני. יש לרענן ולנסות שוב." },
  PRECONDITION_FAILED: { title: "לא ניתן לבצע את הפעולה כעת", detail: "יש להשלים את השלבים הנדרשים ולנסות שוב." },
  VALIDATION_BLOCKED: { title: "הפעולה נחסמה באימות", detail: "יש לתקן את בעיות האימות לפני המשך התהליך." },
  VALIDATION_STALE: { title: "האימות כבר אינו עדכני", detail: "הטיוטה השתנתה מאז האימות. יש להריץ אימות מחדש." },
  VALIDATION_REQUIRED: { title: "נדרש אימות", detail: "יש לאמת את הגרסה הנוכחית לפני המשך התהליך." },
  UNLINKED_CLAIM: { title: "טענה אינה מקושרת לעובדה", detail: "יש לקשר את הטענה לעובדה מאושרת או להסיר אותה." },
  LINEAGE_BROKEN: { title: "מקורות המידע אינם תואמים", detail: "יש לחזור למועמדות ולהמשיך מהמצב העדכני." },
  KNOWLEDGE_REJECTED: { title: "השינוי בעובדה נדחה", detail: "המידע הקיים נשמר. יש לבדוק את פרטי העובדה ולנסות שוב." },
  KNOWLEDGE_RECONCILIATION_REQUIRED: {
    title: "נדרשת התאמת מאגר העובדות",
    detail: "יש להשלים התאמה של מאגר העובדות לפני המשך התהליך.",
  },
  MISSING_FACT_RENDERING: {
    title: "חסר ניסוח בשפת המסמך",
    detail: "יש להשלים ניסוח מתאים לעובדה או להסיר אותה מהבחירה.",
  },
  DUPLICATE_ACKNOWLEDGEMENT_REQUIRED: {
    title: "נמצאה מועמדות דומה",
    detail: "יש לבדוק את ההתאמות ולאשר יצירה של מועמדות נוספת.",
  },
  IDEMPOTENCY_KEY_REUSED: { title: "הבקשה כבר שימשה לפעולה אחרת", detail: "יש לרענן את העמוד ולנסות שוב." },
  SOURCE_CHANGED: { title: "המקור השתנה", detail: "התוצאה לא הופעלה. יש לחזור למצב העדכני ולנסות שוב." },
  WORKING_PROJECTION_DIVERGED: {
    title: "הטיוטה אינה תואמת למצב העדכני",
    detail: "יש לרענן את העמוד ולהמשיך מהטיוטה העדכנית.",
  },
  DEPENDENCY_UNAVAILABLE: { title: "שירות נדרש אינו זמין", detail: "אפשר לנסות שוב מאוחר יותר." },
  INFRASTRUCTURE_FAILURE: { title: "אירעה תקלה בשירות", detail: "המידע הקיים נשמר. אפשר לנסות שוב." },
  NETWORK_UNAVAILABLE: { title: "לא ניתן להגיע לשרת", detail: "יש לבדוק שהשרת פועל ולנסות שוב." },
  INVALID_SERVER_RESPONSE: { title: "התקבלה תשובה לא תקינה", detail: "אפשר לרענן את העמוד ולנסות שוב." },
  UNEXPECTED_HTTP_ERROR: { title: "הבקשה נכשלה", detail: "אפשר לרענן את העמוד ולנסות שוב." },
  METHOD_NOT_ALLOWED: { title: "הפעולה אינה זמינה", detail: "אפשר לרענן את העמוד ולנסות שוב." },
  BODY_LIMIT_EXCEEDED: { title: "המידע שנשלח גדול מדי", detail: "יש לקצר את התוכן ולנסות שוב." },
  PAYLOAD_TOO_LARGE: { title: "המידע שנשלח גדול מדי", detail: "יש לקצר את התוכן ולנסות שוב." },
  ORIGIN_NOT_ALLOWED: { title: "הגישה נדחתה", detail: "יש לפתוח את המערכת מהכתובת שהוגדרה עבורה." },
  INTERNAL_ERROR: { title: "אירעה תקלה בשרת", detail: "המידע הקיים נשמר. אפשר לנסות שוב." },
  SERVICE_UNAVAILABLE: { title: "השירות אינו זמין", detail: "אפשר לנסות שוב מאוחר יותר." },
};

export const localizedProblem = (problem: ProblemDetails): ErrorMessage & { known: boolean } => {
  const translated = problemMessages[problem.code];
  return translated === undefined
    ? { title: "הבקשה נכשלה", detail: problem.detail, known: false }
    : { ...translated, known: true };
};

const fieldLabels: Record<string, string> = {
  company: "חברה",
  role_title: "תפקיד",
  source_url: "קישור למשרה",
  job_text: "תיאור המשרה",
  target_status: "שלב בתהליך",
  reason: "סיבת השינוי",
  next_action: "הפעולה הבאה",
  next_action_date: "תאריך יעד",
  notes: "הערות",
  source: "מקור",
  meaning: "משמעות העובדה",
  renderings: "ניסוח העובדה",
  tags: "תגיות",
  provenance: "מקור המידע",
  resume_style: "סגנון קורות החיים",
};

export const problemFieldIssues = (problem: ProblemDetails): string[] => {
  const issues = problem.context?.issues;
  if (!Array.isArray(issues)) return [];

  return [
    ...new Set(
      issues.flatMap((issue) => {
        if (typeof issue !== "object" || issue === null || !("location" in issue) || !Array.isArray(issue.location)) {
          return [];
        }
        const field = issue.location
          .toReversed()
          .find((part: unknown): part is string => typeof part === "string" && part !== "body");
        return field === undefined ? [] : [`${fieldLabels[field] ?? "אחד השדות"}: הערך אינו תקין.`];
      }),
    ),
  ];
};

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
  "classification-approval-required": "יש להשלים את החלטת הסיווג לפני האימות.",
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
