import type { ApplicationDetail } from "@/api/contracts";
import { outlineClaims } from "@/api/documents";
import { routePaths } from "@/app/routePaths";
import { reasonTitle } from "@/features/preparation";
import { Button } from "@/ui/Button";
import { Callout } from "@/ui/Callout";
import { Card } from "@/ui/Card";
import { Disclosure } from "@/ui/Disclosure";
import type { EditableDocument } from "../model/drafts.types";

export const DraftReviewPanel = ({
  detail,
  draft,
  onNavigate,
  onShowClaim,
}: {
  detail: ApplicationDetail;
  draft: EditableDocument;
  onNavigate: (href: string) => void;
  onShowClaim: (claimId: string) => void;
}) => {
  if (detail.review_reasons.length === 0) return null;
  const claims = outlineClaims(draft.outline);
  return (
    <Card aria-label="החלטות שחוסמות את אישור הטיוטה" className="flex flex-col gap-4 p-5">
      <h2 className="text-body font-semibold text-cv-text">יש לפתור את ההחלטות לפני אישור הטיוטה</h2>
      {detail.review_reasons.map((reason) => {
        const pending = reason.code === "PENDING_FACT_REQUIRES_RESOLUTION";
        const deleted = reason.code === "FACT_DELETED_REQUIRES_RESOLUTION";
        const claim = pending
          ? claims.find((item) => item.claim_type === "pending")
          : deleted
            ? claims.find((item) => item.fact_ids.includes(reason.entity_references.fact_id ?? ""))
            : undefined;
        const editableClaim =
          claim !== undefined &&
          draft.outline.sections.some((section) => section.claims.some((item) => item.claim_id === claim.claim_id));
        const editAllowed = reason.allowed_resolution_actions.some((action) =>
          ["edit", "update_selection", "confirm_and_use_fact"].includes(action),
        );
        const selectionAllowed = reason.allowed_resolution_actions.includes("update_selection");
        return (
          <Callout
            key={reason.code}
            title={reasonTitle(reason.code, "נדרשת החלטה לפני אישור")}
            tone="blocker"
            action={
              claim !== undefined && editAllowed ? (
                <Button variant="secondary" onClick={() => onShowClaim(claim.claim_id)}>
                  {pending ? "מעבר לפתרון השורה" : "מעבר לשורה להסרת התלות בעובדה"}
                </Button>
              ) : selectionAllowed ? (
                <Button variant="secondary" onClick={() => onNavigate(routePaths.application(detail.application.id))}>
                  פתרון בחירת העובדות בהכנה
                </Button>
              ) : undefined
            }
          >
            <p>יש להשלים את ההחלטה הזו לפני שאפשר להכין את קובץ ה־PDF.</p>
            {claim !== undefined && editAllowed ? (
              <p>
                {pending
                  ? editableClaim
                    ? "יש להשתמש באפשרויות לצד השורה: בדיקת הניסוח מול העובדות שמתחתיו, אישור ושימוש בעובדה כאשר ההקשר מאפשר זאת, או תיקון והסרת תוכן שאינו נתמך. יצירת עובדה ממתינה לבדה אינה מתירה אישור."
                    : `השורה "${claim.text}" בכותרת או בפרטי הקשר נערכה לנוסח שאינו נתמך. עריכה חוזרת שלה פותרת זאת: כותרת עוברת אימות מול הנוסחים שהפרופיל מאשר, ושורת קשר חוזרת לנוסח המקורי שלה.`
                  : "עובדה שנמחקה אינה ניתנת לקידום. יש להסיר את התלות בה או לבחור עובדה קנונית תקפה; אין לשנות את העובדה ההיסטורית."}
              </p>
            ) : selectionAllowed ? (
              <p>יש לשנות את בחירת העובדות של המסמך. טופס החלטות הסיווג אינו פותר את החסר הזה.</p>
            ) : (
              <p>
                {reason.code === "KNOWLEDGE_RECONCILIATION_REQUIRED"
                  ? "נדרשת השלמת התאמה של מאגר הידע. טופס החלטות הניתוח אינו פותר זאת, ואין בעורך פעולה זמינה שסוגרת את החסם."
                  : "אין בעורך פעולה זמינה שסוגרת את הסיבה הזו בהקשר הנוכחי. יש לפתור את התלות במקור לפני המשך; טופס החלטות הניתוח אינו פותר אותה."}
              </p>
            )}
            {/* The server's sentence is evidence, not the explanation: it is English and
                written for a log, so it stays folded as it is in PreparationAlerts. */}
            <Disclosure summary="פרטי הסיבה">
              <p dir="auto">{reason.message}</p>
            </Disclosure>
          </Callout>
        );
      })}
    </Card>
  );
};
