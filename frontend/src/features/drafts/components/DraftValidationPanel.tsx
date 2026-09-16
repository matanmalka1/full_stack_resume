import { briefServerFailureDetail, ErrorCallout } from "@/ui/ErrorCallout";
import { Callout } from "@/ui/Callout";
import { ValidationReportView } from "@/features/revisions";
import type { DraftValidation } from "../hooks/useDraftValidation";

interface DraftValidationPanelProps {
  validation: DraftValidation;
}

/* A.4 frame 5's result, as a panel of the editor rather than a screen of its own. The
   draft it describes is the one in the editor beside it, so making the user leave to read
   the verdict - and come back to fix it - was the trip this removes.

   It draws the run and runs the command. What follows from the run - whether approval is
   open - is derived upstream from the same values, so nothing is reported back out of
   here through an effect. */
export const DraftValidationPanel = ({ validation }: DraftValidationPanelProps) => {
  const { error, run, stale } = validation;

  return (
    <section aria-labelledby="validation-summary" className="flex flex-col gap-3 border-t border-cv-border pt-4">
      <h2 className="text-heading-sm font-bold text-cv-text" id="validation-summary">
        {run === undefined ? "בדיקת הקובץ" : run.passed ? "הקובץ עבר בדיקה" : "נדרשים תיקונים בקובץ"}
      </h2>

      {stale ? (
        <Callout title="הטיוטה השתנתה מאז הבדיקה" tone="warning">
          יש לבדוק מחדש את הגרסה הנוכחית לפני הכנת ה־PDF.
        </Callout>
      ) : null}

      {error === null || error === undefined ? null : (
        <ErrorCallout
          error={error}
          fallbackDetail={briefServerFailureDetail}
          fallbackTitle="לא ניתן להשלים את בדיקת הקובץ"
        />
      )}

      {run === undefined ? (
        <p className="text-support leading-6 text-cv-text-muted">
          הבדיקה תופעל מכפתור הכנת ה־PDF ותוודא שהגרסה המוצגת מוכנה למסירה.
        </p>
      ) : (
        <ValidationReportView report={run.report} />
      )}
    </section>
  );
};
