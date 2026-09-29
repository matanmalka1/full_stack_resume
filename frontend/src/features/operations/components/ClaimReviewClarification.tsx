import { Link } from "react-router-dom";

import type { Operation } from "@/api/contracts";
import { routePaths } from "@/app/routePaths";
import { buttonClasses } from "@/ui/Button";

type ReviewReason = Extract<NonNullable<Operation["failure_reason"]>, { code: "claim_review" }>;

export const ClaimReviewClarification = ({
  operation,
  reason,
  onNavigate,
}: {
  operation: Operation;
  reason: ReviewReason;
  onNavigate?: (() => void) | undefined;
}) => (
  <section aria-label="בירור הניסוח שנדחה" className="flex flex-col gap-4">
    <p className="text-support text-cv-text-muted">
      ההצעה לא הופעלה. אלה הניסוח והמקורות בזמן הבדיקה; המסמך והעובדות עשויים להשתנות מאז. אישור קורות החיים אינו מאשר
      את ההצעה הזו.
    </p>
    {reason.claims.map((claim) => (
      <div className="flex flex-col gap-3 border-t border-cv-border pt-3" key={claim.claim_id}>
        <p className="font-semibold" dir="auto">
          {claim.heading ?? claim.section}
        </p>
        <p className="text-support text-cv-text-muted" dir="auto">
          {claim.section}
        </p>
        <blockquote className="border-s-2 border-cv-border ps-3" dir="auto">
          {claim.text}
        </blockquote>
        <p>
          {claim.verdict === "uncertain"
            ? "הבדיקה לא הצליחה לקבוע שהמקורות תומכים בניסוח."
            : "הניסוח לא עבר את בדיקת התמיכה בעובדות."}
        </p>
        <ul aria-label="המקורות שנבדקו" className="flex flex-col gap-3">
          {claim.sources.map((source) => (
            <li className="bg-cv-surface-muted p-3" key={source.fact_id}>
              <p dir="auto">{source.rendering}</p>
              {source.meaning === source.rendering ? null : (
                <p className="mt-1 text-support text-cv-text-muted" dir="auto">
                  {source.meaning}
                </p>
              )}
              <Link
                onClick={onNavigate}
                className="text-support text-cv-accent underline"
                to={`${routePaths.facts}?${new URLSearchParams({ fact: source.fact_id })}`}
              >
                פתיחת העובדה הנוכחית
              </Link>
            </li>
          ))}
        </ul>
        <p className="font-medium">האם אפשר להסתפק בנוסח נתמך, או שחסר מידע עובדתי במקורות?</p>
        <p className="text-support text-cv-text-muted">
          אפשר להשאיר את המסמך כפי שהוא. לתיקון, פתחו את המסמך וערכו או הסירו את השורה; ניסוח חדש ייבדק שוב. מידע חדש יש
          להוסיף ולאשר במאגר העובדות לפני שימוש בו.
        </p>
        <div className="flex flex-wrap gap-3">
          <Link
            onClick={onNavigate}
            className={buttonClasses("secondary")}
            to={
              operation.operation_type === "create_draft"
                ? routePaths.application(operation.application_id)
                : `${routePaths.draft(operation.application_id)}?${new URLSearchParams({ claim: claim.claim_id })}`
            }
          >
            {operation.operation_type === "create_draft" ? "חזרה להכנת טיוטה" : "פתיחת השורה במסמך"}
          </Link>
          <Link className={buttonClasses("secondary")} onClick={onNavigate} to={routePaths.facts}>
            הוספת מידע עובדתי
          </Link>
        </div>
      </div>
    ))}
  </section>
);
