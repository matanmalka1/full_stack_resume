import { ArrowLeft } from "lucide-react";

import type { ApplicationDetail } from "@/api/contracts";
import { Button } from "@/ui/Button";
import { surfaceClasses } from "@/ui/surface";
import { PreparationStatusBadges } from "@/features/preparation";
import { RecruitmentSummary } from "@/features/recruitment";

/* What is outstanding on the preparation axis, as one line rather than as the alert
   stack the preparation tab already draws in full. The counts come from the projection;
   nothing here re-derives whether they block anything - that is what the tab is for, and
   the button goes there. */
const attentionSummary = (detail: ApplicationDetail, openDecisionsCount: number): string | null => {
  const outstanding = [
    openDecisionsCount === 0
      ? null
      : openDecisionsCount === 1
        ? "החלטה אחת ממתינה"
        : `${openDecisionsCount} החלטות ממתינות`,
    detail.stale_reasons.length === 0 ? null : "הטיוטה אינה מעודכנת מול המקורות",
    detail.warnings.length === 0
      ? null
      : detail.warnings.length === 1
        ? "אזהרה אחת"
        : `${detail.warnings.length} אזהרות`,
  ].filter((entry): entry is string => entry !== null);

  return outstanding.length === 0 ? null : outstanding.join(" · ");
};

/* The two axes of one Application, side by side and never merged.

   Preparation says where the CV stands; recruitment says where the application stands
   with the employer. They move independently - a CV can be Ready while the recruitment
   status is still "נשמר", and an interview can be scheduled against a draft that was
   never finished - so drawing them as one row of badges, or as one linear track, would
   claim a sequence that does not exist. Two columns under two headings is the whole
   design.

   Neither column owns its own vocabulary: the badges are preparation's and the
   recruitment block is the recruitment feature's own summary, composed here rather than
   restated. */
export const ApplicationStatePanel = ({
  detail,
  onOpenPreparation,
  openDecisionsCount,
}: {
  detail: ApplicationDetail;
  onOpenPreparation: () => void;
  openDecisionsCount: number;
}) => {
  const attention = attentionSummary(detail, openDecisionsCount);

  return (
    <section aria-labelledby="application-state-heading" className="grid gap-4 sm:grid-cols-2">
      <h2 className="sr-only" id="application-state-heading">
        מצב המועמדות בשני הצירים
      </h2>

      <div className="flex min-w-0 flex-col gap-2">
        <h3 className="text-support font-semibold text-cv-text-muted">הכנת קורות חיים</h3>
        <div className={surfaceClasses("flex h-full flex-col gap-3 bg-cv-surface-muted p-4 shadow-inner")}>
          <PreparationStatusBadges className="flex flex-wrap items-center gap-2" detail={detail} />

          <p
            className={attention === null ? "text-support text-cv-text-muted" : "text-support font-medium text-cv-text"}
          >
            {attention ?? "אין החלטה או אזהרה פתוחה."}
          </p>

          <Button className="mt-auto w-fit px-0!" onClick={onOpenPreparation} variant="ghost">
            מעבר להכנת קורות החיים
            <ArrowLeft aria-hidden="true" className="size-4 shrink-0" />
          </Button>
        </div>
      </div>

      <div className="flex min-w-0 flex-col gap-2">
        <h3 className="text-support font-semibold text-cv-text-muted">גיוס</h3>
        <RecruitmentSummary detail={detail} />
      </div>
    </section>
  );
};
