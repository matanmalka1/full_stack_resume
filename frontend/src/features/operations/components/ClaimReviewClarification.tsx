import { Link } from "react-router-dom";

import type { Operation } from "@/api/contracts";
import { routePaths } from "@/app/routePaths";
import { buttonClasses } from "@/ui/Button";
import { StatusBadge } from "@/ui/StatusBadge";

type ReviewReason = Extract<NonNullable<Operation["failure_reason"]>, { code: "claim_review" }>;
type RejectedClaim = ReviewReason["claims"][number];
type ReviewProblem = NonNullable<RejectedClaim["problems"]>[number];

const verdictLabels: Record<RejectedClaim["verdict"], string> = {
  uncertain: "לא הוכרע",
  unsupported: "לא נתמך",
  unattested: "הראיות לא אומתו",
  refused: "נדחה לפני בדיקה",
};

/* The checks a `supported` answer's evidence failed. The reviewer said yes, so its own
   explanation reads as approval; only these say why the line was still refused. Keyed by
   the generated union, so a new check fails the build until it is worded here. */
const problemLabels: Record<ReviewProblem, string> = {
  "invalid-review-evidence": "הבודק לא פירט על מה נשען אישור השורה.",
  "incomplete-review-coverage": "הבודק לא בדק את כל השורה - חלק מהניסוח לא נבדק מול העובדות.",
  "invalid-review-claim-quote": "הבודק ציטט מהשורה ניסוח שאינו מופיע בה.",
  "invalid-review-source-quote": "הבודק ציטט מהעובדות טקסט שאינו מופיע בהן.",
  "stale-review-source": "השורה מקושרת לעובדה שאינה מאושרת עוד.",
  "review-fact-coverage-mismatch":
    "השורה נשענת על עובדה שאינה מקושרת אליה, או מקושרת לעובדה שלא שימשה בה. לרוב זה ניסוח (כמו תואר תפקיד) שנלקח מעובדה אחרת.",
  "unsupported-review-number": "השורה כוללת מספר שאינו מופיע בעובדות שלה.",
};

/* Where the line sat. The heading is the section's own title more often than not, and
   printing the same words twice as title and subtitle only looked like a second fact. */
const claimContext = ({ heading, section }: RejectedClaim) =>
  heading == null || heading === section ? section : `${section} · ${heading}`;

const FieldLabel = ({ children }: { children: string }) => (
  <p className="text-support font-medium text-cv-text-muted">{children}</p>
);

/* Two uses, one panel. On a failure the callout above already names the verdict and that
   nothing was applied; the panel adds only what the callout cannot: which line, what it
   said, the facts it was checked against as they were read then, and where to fix it.
   On a success (`withheld`) the rest of the answer was written, and these are the lines
   that were not: each kept the wording it had before the run. */
export const ClaimReviewClarification = ({
  operation,
  reason,
  withheld = false,
  onNavigate,
}: {
  operation: Operation;
  reason: ReviewReason;
  withheld?: boolean;
  onNavigate?: (() => void) | undefined;
}) => {
  /* A refused first draft left no document to open a line in; a withheld line has one. */
  const noDocument = !withheld && operation.operation_type === "create_draft";
  /* On a failure a verdict per line only says something when the lines disagree;
     otherwise it is the callout's title again. A success has no such title. */
  const showVerdicts = withheld || new Set(reason.claims.map((claim) => claim.verdict)).size > 1;

  return (
    <section aria-label={withheld ? "שורות שלא עודכנו" : "בירור הניסוח שנדחה"} className="flex flex-col gap-4">
      <p className="text-support text-cv-text-muted">
        {withheld
          ? operation.operation_type === "create_draft"
            ? "הטיוטה נוצרה. השורות הבאות נשארו בנוסח שהורכב ישירות מהעובדות, כי הניסוח שהוצע להן לא אושר."
            : "שאר השינויים נשמרו. השורות הבאות נשארו בנוסח הקודם שלהן, כי הניסוח שהוצע להן לא אושר."
          : noDocument
            ? "לא נוצרה טיוטה."
            : "המסמך לא השתנה."}{" "}
        להלן הניסוח שנדחה והעובדות שמולן נבדק, כפי שהיו בזמן הבדיקה; ייתכן שהשתנו מאז.
      </p>

      {reason.claims.map((claim) => (
        <article className="flex flex-col gap-3 rounded-surface border border-cv-border p-4" key={claim.claim_id}>
          <header className="flex flex-wrap items-center justify-between gap-2">
            <p className="font-semibold" dir="auto">
              {claimContext(claim)}
            </p>
            {showVerdicts ? (
              <StatusBadge tone={claim.verdict === "uncertain" ? "warning" : "blocker"}>
                {verdictLabels[claim.verdict]}
              </StatusBadge>
            ) : null}
          </header>

          <div className="flex flex-col gap-1">
            <FieldLabel>הניסוח שנדחה</FieldLabel>
            <blockquote className="border-s-2 border-cv-border ps-3" dir="auto">
              {claim.text}
            </blockquote>
          </div>

          {claim.verdict === "refused" ? (
            <p className="text-support text-cv-text-muted">
              הניסוח לא הגיע לבדיקה: הוא קושר לעובדה שלא ניתנה למשימה, לא קושר לאף עובדה, או שלא ניתן היה להחיל אותו.
            </p>
          ) : null}

          {claim.problems == null || claim.problems.length === 0 ? null : (
            <div className="flex flex-col gap-1">
              <FieldLabel>למה השורה נדחתה</FieldLabel>
              <ul className="list-disc ps-5">
                {claim.problems.map((problem) => (
                  <li key={problem}>{problemLabels[problem]}</li>
                ))}
              </ul>
            </div>
          )}

          {/* The reviewer's words, in its own language. Without them a sentence almost
              identical to its fact is refused and nothing says why; with them, the
              reader still has to be told this is a reading, not a proof. */}
          {claim.rationale == null ? null : (
            <div className="flex flex-col gap-1">
              <FieldLabel>הסבר הבודק</FieldLabel>
              <p dir="auto">{claim.rationale}</p>
              <p className="text-support text-cv-text-muted">זו הקריאה של הבודק האוטומטי, לא הוכחה.</p>
            </div>
          )}

          <div className="flex flex-col gap-1">
            <FieldLabel>{claim.sources.length > 1 ? "העובדות שנבדקו" : "העובדה שנבדקה"}</FieldLabel>
            <ul aria-label="המקורות שנבדקו" className="flex flex-col gap-2">
              {claim.sources.map((source) => (
                <li className="flex flex-col gap-2 rounded-surface bg-cv-surface-muted p-3" key={source.fact_id}>
                  {/* The meaning is what the review holds the wording to; the rendering is
                      how the CV prints the fact. Where they differ - a qualifier one
                      carries and the other drops - is usually the reason, so both show,
                      each named. */}
                  <div>
                    <p className="text-support text-cv-text-muted">משמעות</p>
                    <p dir="auto">{source.meaning}</p>
                  </div>
                  {source.meaning === source.rendering ? null : (
                    <div>
                      <p className="text-support text-cv-text-muted">נוסח בקורות החיים</p>
                      <p dir="auto">{source.rendering}</p>
                    </div>
                  )}
                  <Link
                    onClick={onNavigate}
                    className="self-start text-support text-cv-accent underline"
                    to={`${routePaths.facts}?${new URLSearchParams({ fact: source.fact_id })}`}
                  >
                    פתיחת העובדה הנוכחית
                  </Link>
                </li>
              ))}
            </ul>
          </div>

          {noDocument ? null : (
            <Link
              onClick={onNavigate}
              className={buttonClasses("secondary", "self-start")}
              to={`${routePaths.draft(operation.application_id)}?${new URLSearchParams({ claim: claim.claim_id })}`}
            >
              פתיחת השורה במסמך
            </Link>
          )}
        </article>
      ))}

      <p className="text-support text-cv-text-muted">
        {noDocument
          ? "אפשר להריץ שוב את יצירת הטיוטה. אם חסר מידע במקורות, יש להוסיף אותו במאגר העובדות ולאשר אותו לפני שימוש בו."
          : "אפשר להשאיר את המסמך כפי שהוא, או לערוך או להסיר את השורה - ניסוח חדש ייבדק שוב. אם חסר מידע במקורות, יש להוסיף אותו במאגר העובדות ולאשר אותו לפני שימוש בו."}
      </p>
      <div className="flex flex-wrap gap-3">
        {noDocument ? (
          <Link
            onClick={onNavigate}
            className={buttonClasses("secondary")}
            to={routePaths.application(operation.application_id)}
          >
            חזרה להכנת טיוטה
          </Link>
        ) : null}
        <Link className={buttonClasses("secondary")} onClick={onNavigate} to={routePaths.facts}>
          הוספת מידע עובדתי
        </Link>
      </div>
    </section>
  );
};
