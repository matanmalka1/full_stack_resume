import { Link } from "react-router-dom";

import type { Operation } from "@/api/contracts";
import { routePaths } from "@/app/routePaths";
import { buttonClasses } from "@/ui/Button";
import { StatusBadge } from "@/ui/StatusBadge";

type ReviewReason = Extract<NonNullable<Operation["failure_reason"]>, { code: "claim_review" }>;
type RejectedClaim = ReviewReason["claims"][number];

const verdictLabels: Record<RejectedClaim["verdict"], string> = {
  uncertain: "לא הוכרע",
  unsupported: "לא נתמך",
};

/* Where the line sat. The heading is the section's own title more often than not, and
   printing the same words twice as title and subtitle only looked like a second fact. */
const claimContext = ({ heading, section }: RejectedClaim) =>
  heading == null || heading === section ? section : `${section} · ${heading}`;

const FieldLabel = ({ children }: { children: string }) => (
  <p className="text-support font-medium text-cv-text-muted">{children}</p>
);

/* The failure callout above already names the verdict and that nothing was applied. This
   panel adds only what the callout cannot: which line, what it said, the facts it was
   checked against as they were read then, and where to fix it. */
export const ClaimReviewClarification = ({
  operation,
  reason,
  onNavigate,
}: {
  operation: Operation;
  reason: ReviewReason;
  onNavigate?: (() => void) | undefined;
}) => {
  const initialDraft = operation.operation_type === "create_draft";
  /* A verdict per line only says something when the lines disagree; otherwise it is the
     callout's title again. */
  const mixedVerdicts = new Set(reason.claims.map((claim) => claim.verdict)).size > 1;

  return (
    <section aria-label="בירור הניסוח שנדחה" className="flex flex-col gap-4">
      <p className="text-support text-cv-text-muted">
        {initialDraft ? "לא נוצרה טיוטה." : "המסמך לא השתנה."} להלן הניסוח שנדחה והעובדות שמולן נבדק, כפי שהיו בזמן
        הבדיקה; ייתכן שהשתנו מאז.
      </p>

      {reason.claims.map((claim) => (
        <article className="flex flex-col gap-3 rounded-surface border border-cv-border p-4" key={claim.claim_id}>
          <header className="flex flex-wrap items-center justify-between gap-2">
            <p className="font-semibold" dir="auto">
              {claimContext(claim)}
            </p>
            {mixedVerdicts ? (
              <StatusBadge tone={claim.verdict === "unsupported" ? "blocker" : "warning"}>
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

          {initialDraft ? null : (
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
        {initialDraft
          ? "אפשר להריץ שוב את יצירת הטיוטה. אם חסר מידע במקורות, יש להוסיף אותו במאגר העובדות ולאשר אותו לפני שימוש בו."
          : "אפשר להשאיר את המסמך כפי שהוא, או לערוך או להסיר את השורה - ניסוח חדש ייבדק שוב. אם חסר מידע במקורות, יש להוסיף אותו במאגר העובדות ולאשר אותו לפני שימוש בו."}
      </p>
      <div className="flex flex-wrap gap-3">
        {initialDraft ? (
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
