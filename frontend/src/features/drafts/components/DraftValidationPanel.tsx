import { briefServerFailureDetail, ErrorCallout } from "@/ui/ErrorCallout";
import { Button } from "@/ui/Button";
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
  const { canValidate, error, isPending, run, stale, validate } = validation;

  return (
    <section aria-labelledby="validation-summary" className="flex flex-col gap-3 border-t border-cv-border pt-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h2 className="text-heading-sm font-bold text-cv-text" id="validation-summary">
          {run === undefined ? "אימות הטיוטה" : run.passed ? "הטיוטה עברה אימות" : "הטיוטה לא עברה אימות"}
        </h2>
        <Button disabled={!canValidate} onClick={validate} pending={isPending} pendingLabel="מאמת…" variant="secondary">
          {run === undefined ? "אימות הטיוטה" : "אימות מחדש"}
        </Button>
      </div>

      {stale ? (
        <Callout title="הטיוטה השתנתה מאז האימות" tone="warning">
          יש להריץ אימות חדש לגרסה הנוכחית. לא הופעל אישור ולא בוצע אימות מחדש אוטומטי.
        </Callout>
      ) : null}

      {error === null || error === undefined ? null : (
        <ErrorCallout
          error={error}
          fallbackDetail={briefServerFailureDetail}
          fallbackTitle="לא ניתן להשלים את האימות"
        />
      )}

      {run === undefined ? (
        <p className="text-support leading-6 text-cv-text-muted">
          האימות בודק את גרסת הטיוטה המדויקת שמוצגת כאן, לפני אישור.
        </p>
      ) : (
        <ValidationReportView report={run.report} />
      )}
    </section>
  );
};
