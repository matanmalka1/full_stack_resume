import { ArrowLeft, OctagonAlert } from "lucide-react";

import type { ApplicationDetail, DraftClaim } from "@/api/contracts";
import { outlineClaims } from "@/api/documents";
import { routePaths } from "@/app/routePaths";
import { reasonTitle } from "@/features/preparation";
import { Button } from "@/ui/Button";
import { Callout } from "@/ui/Callout";
import { Disclosure } from "@/ui/Disclosure";
import type { EditableDocument } from "../model/drafts.types";

type ReviewReason = ApplicationDetail["review_reasons"][number];

interface DraftAttentionPanelProps {
  detail: ApplicationDetail;
  draft: EditableDocument;
  onNavigate: (href: string) => void;
  onShowClaim: (claimId: string) => void;
  /* Every line nothing authorizes, in reading order. Each blocks approval where it sits. */
  unsupportedClaims: DraftClaim[];
}

const ReasonCallout = ({
  detail,
  draft,
  onNavigate,
  onShowClaim,
  reason,
}: Omit<DraftAttentionPanelProps, "unsupportedClaims"> & { reason: ReviewReason }) => {
  const claims = outlineClaims(draft.outline);
  const pending = reason.code === "PENDING_FACT_REQUIRES_RESOLUTION";
  const deleted = reason.code === "FACT_DELETED_REQUIRES_RESOLUTION";
  const claim = pending
    ? claims.find((item) => item.claim_type === "pending")
    : deleted
      ? claims.find((item) => item.fact_ids.includes(reason.entity_references.fact_id ?? ""))
      : undefined;
  const inSections =
    claim !== undefined &&
    draft.outline.sections.some((section) => section.claims.some((item) => item.claim_id === claim.claim_id));
  const editAllowed = reason.allowed_resolution_actions.some((action) =>
    ["edit", "update_selection", "confirm_and_use_fact"].includes(action),
  );
  const selectionAllowed = reason.allowed_resolution_actions.includes("update_selection");
  const toClaim = claim !== undefined && editAllowed;

  return (
    <Callout
      action={
        toClaim ? (
          <Button onClick={() => onShowClaim(claim.claim_id)} variant="secondary">
            {pending ? "מעבר לפתרון השורה" : "מעבר לשורה להסרת התלות בעובדה"}
          </Button>
        ) : selectionAllowed ? (
          <Button onClick={() => onNavigate(routePaths.application(detail.application.id))} variant="secondary">
            פתרון בחירת העובדות בהכנה
          </Button>
        ) : undefined
      }
      title={reasonTitle(reason.code, "נדרשת החלטה לפני אישור")}
      tone="blocker"
    >
      <p>
        {toClaim
          ? pending
            ? inSections
              ? "בשורה יש אפשרויות לפתרון: בדיקת הניסוח מול העובדות, הפיכת הטקסט לעובדה מאושרת, או תיקון והסרה. עובדה ממתינה לבדה אינה מתירה אישור."
              : `השורה "${claim.text}" בכותרת או בפרטי הקשר נערכה לנוסח שאינו נתמך. עריכה חוזרת שלה פותרת זאת.`
            : "עובדה שנמחקה אינה ניתנת לקידום. יש להסיר את התלות בה או לבחור עובדה תקפה; העובדה ההיסטורית לא משתנה."
          : selectionAllowed
            ? "יש לשנות את בחירת העובדות של המסמך במסך ההכנה."
            : reason.code === "KNOWLEDGE_RECONCILIATION_REQUIRED"
              ? "נדרשת השלמת התאמה של מאגר הידע. אין בעורך פעולה שסוגרת את החסם הזה."
              : "אין בעורך פעולה שסוגרת את הסיבה הזו. יש לפתור את התלות במקור לפני המשך."}
      </p>
      {/* The server's sentence is evidence, not the explanation: it is English and written
          for a log, so it stays folded as it is in PreparationAlerts. */}
      <Disclosure summary="פרטי הסיבה">
        <p dir="auto">{reason.message}</p>
      </Disclosure>
    </Callout>
  );
};

/* Everything standing between this draft and its approval, in one place, each with the
   way to it.

   Two sources, both the server's: the projection's review reasons, and the lines the
   outline itself marks as backed by nothing. The reasons were a card of their own and the
   unsupported lines were only findable by scrolling the whole document for a red badge;
   the reader now sees the full list first and jumps to each line from it. Silent when
   there is nothing to do. */
export const DraftAttentionPanel = ({
  detail,
  draft,
  onNavigate,
  onShowClaim,
  unsupportedClaims,
}: DraftAttentionPanelProps) => {
  if (detail.review_reasons.length === 0 && unsupportedClaims.length === 0) return null;

  return (
    <section
      aria-labelledby="draft-attention-heading"
      className="flex flex-col gap-3 border border-cv-blocker/30 bg-cv-surface p-card-padding"
    >
      <h2 className="flex items-center gap-2 text-body font-semibold text-cv-text" id="draft-attention-heading">
        <OctagonAlert aria-hidden="true" className="size-icon-md text-cv-blocker" />
        לטיפול לפני אישור
      </h2>

      {detail.review_reasons.map((reason) => (
        <ReasonCallout
          detail={detail}
          draft={draft}
          key={reason.code}
          onNavigate={onNavigate}
          onShowClaim={onShowClaim}
          reason={reason}
        />
      ))}

      {unsupportedClaims.length === 0 ? null : (
        <div className="flex flex-col gap-1">
          <p className="text-support font-semibold text-cv-text">
            {unsupportedClaims.length === 1
              ? "שורה אחת בלי עובדה מאחוריה"
              : `${unsupportedClaims.length} שורות בלי עובדה מאחוריהן`}
          </p>
          <ul className="flex flex-col divide-y divide-cv-border">
            {unsupportedClaims.map((claim) => (
              <li className="flex items-center justify-between gap-3 py-1.5" key={claim.claim_id}>
                {/* Quoted: it is a line of the document named here, not text of the panel. */}
                <p className="line-clamp-2 min-w-0 text-support leading-6 text-cv-text" dir="auto">
                  „{claim.text}”
                </p>
                <Button
                  aria-label={`מעבר לשורה: ${claim.text}`}
                  className="shrink-0"
                  onClick={() => onShowClaim(claim.claim_id)}
                  variant="ghost"
                >
                  מעבר לשורה
                  <ArrowLeft aria-hidden="true" className="size-icon-md" />
                </Button>
              </li>
            ))}
          </ul>
        </div>
      )}
    </section>
  );
};
