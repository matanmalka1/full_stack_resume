import { ArrowLeft, OctagonAlert } from "lucide-react";

import type { ApplicationDetail, DraftClaim } from "@/api/contracts";
import { outlineClaims } from "@/api/documents";
import { ReasonCallout } from "@/features/preparation";
import { Button } from "@/ui/Button";
import { cardClasses } from "@/ui/surface";
import type { EditableDocument } from "../model/drafts.types";

type ReviewReason = ApplicationDetail["review_reasons"][number];

interface DraftAttentionPanelProps {
  detail: ApplicationDetail;
  draft: EditableDocument;
  onShowClaim: (claimId: string) => void;
  /* Every line nothing authorizes, in reading order. Each blocks approval where it sits. */
  unsupportedClaims: DraftClaim[];
}

/* Every line nothing authorizes, each with the way to it. Quoted: it is a line of the
   document named here, not text of the panel. */
const UnsupportedLines = ({
  claims,
  onShowClaim,
}: {
  claims: DraftClaim[];
  onShowClaim: (claimId: string) => void;
}) => (
  <div className="flex flex-col gap-1">
    <p className="text-support font-semibold text-cv-text">
      {claims.length === 1 ? "שורה אחת בלי עובדה מאחוריה" : `${claims.length} שורות בלי עובדה מאחוריהן`}
    </p>
    <ul className="flex flex-col divide-y divide-cv-border">
      {claims.map((claim) => (
        <li className="flex items-center justify-between gap-3 py-1" key={claim.claim_id}>
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
);

const DraftReasonCallout = ({
  draft,
  onShowClaim,
  reason,
  unsupportedClaims,
}: Omit<DraftAttentionPanelProps, "detail"> & { reason: ReviewReason }) => {
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
    ["edit", "confirm_and_use_fact"].includes(action),
  );
  const toClaim = claim !== undefined && editAllowed;

  return (
    <ReasonCallout
      action={
        toClaim ? (
          <Button onClick={() => onShowClaim(claim.claim_id)} variant="secondary">
            {pending ? "מעבר לפתרון השורה" : "מעבר לשורה להסרת התלות בעובדה"}
          </Button>
        ) : undefined
      }
      fallbackTitle="נדרשת החלטה לפני אישור"
      reason={reason}
      tone="blocker"
    >
      <p>
        {toClaim
          ? pending
            ? inSections
              ? "בשורה יש אפשרויות לפתרון: בדיקת הניסוח מול העובדות, הפיכת הטקסט לעובדה מאושרת, או תיקון והסרה. עובדה ממתינה לבדה אינה מתירה אישור."
              : `השורה "${claim.text}" בכותרת או בפרטי הקשר נערכה לנוסח שאינו נתמך. עריכה חוזרת שלה פותרת זאת.`
            : "עובדה שנמחקה אינה ניתנת לקידום. יש להסיר את התלות בה או לבחור עובדה תקפה; העובדה ההיסטורית לא משתנה."
          : "אין בעורך פעולה שסוגרת את הסיבה הזו. יש לפתור את התלות במקור לפני המשך."}
      </p>
      {pending && unsupportedClaims.length > 0 ? (
        <div className="mt-2">
          <UnsupportedLines claims={unsupportedClaims} onShowClaim={onShowClaim} />
        </div>
      ) : null}
    </ReasonCallout>
  );
};

/* What the projection says stands between this draft and its approval, each reason with
   the way to it.

   The lines the outline marks as backed by nothing are not listed here on their own: the
   design marks them where they stand - a dot on their part in the navigation, a recessed
   row with its answers under it. They are listed only inside the projection's own
   pending-fact reason, which is about exactly them. Silent when the projection names
   nothing. */
export const DraftAttentionPanel = ({ detail, draft, onShowClaim, unsupportedClaims }: DraftAttentionPanelProps) => {
  if (detail.review_reasons.length === 0) return null;

  return (
    <section aria-labelledby="draft-attention-heading" className={cardClasses("flex flex-col gap-3 p-4 max-lg:p-3.5")}>
      <h2 className="flex items-center gap-2 text-body font-semibold text-cv-text" id="draft-attention-heading">
        <OctagonAlert aria-hidden="true" className="size-icon-md text-cv-blocker" />
        לטיפול לפני אישור
      </h2>

      {detail.review_reasons.map((reason) => (
        <DraftReasonCallout
          draft={draft}
          key={reason.code}
          onShowClaim={onShowClaim}
          reason={reason}
          unsupportedClaims={unsupportedClaims}
        />
      ))}
    </section>
  );
};
