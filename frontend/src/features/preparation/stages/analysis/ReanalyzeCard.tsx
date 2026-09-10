import type { ApplicationDetail } from "@/api/contracts";
import { Button } from "@/ui/Button";
import { useAnalyzeCommand } from "../../api/mutations";
import type { WorkflowActionPlan } from "../../model/workflowActionPlan";

/* Re-running the analysis, beside the analysis it would replace - in the diagnostics tab,
   not among the workflow's own next steps.

   It used to sit in `WorkflowActions`, in the same row as "יצירת טיוטה": the one action
   the workflow is actually waiting for shared a shelf with one that is worth pressing only
   when the classification above looks wrong. Nothing here changes what the command does -
   it is the same `analyze` mutation `WorkflowActions` sends for a first analysis, only
   offered from where the analysis being reconsidered is on screen. `WorkflowActions`
   still owns the first analyze of an Application that has none: there is no diagnostics
   tab yet for that case to live in. */
export const ReanalyzeCard = ({
  detail,
  onQueued,
  plan,
}: {
  detail: ApplicationDetail;
  onQueued: (operationId: string) => void;
  plan: WorkflowActionPlan;
}) => {
  const { analyze, settings } = useAnalyzeCommand(detail, onQueued);

  if (plan.analyze === null || !plan.analyze.reanalysis) {
    return null;
  }

  return (
    /* No rule of its own: the panel's `divide-y` draws the one above it, in the same
       rhythm as every finding it follows. */
    <div className="flex flex-wrap items-center justify-between gap-4">
      <p className="max-w-md text-support leading-6 text-cv-text-muted">
        {plan.draftWouldReplace
          ? "ניתוח מחדש יוצר ניתוח חדש ונפרד לאותו תצלום משרה. הטיוטה הפעילה נשמרת כפי שהיא, אך תסומן כלא מעודכנת מולו."
          : "ניתוח מחדש כדאי רק אם הסיווג שלמעלה נראה שגוי. הוא יוצר ניתוח חדש ונפרד לאותו תצלום משרה, ואינו מושך נוסח משרה מעודכן."}
      </p>
      <Button
        disabled={settings === undefined}
        onClick={() => analyze.mutate()}
        pending={analyze.isPending}
        pendingLabel="מפעיל ניתוח…"
        variant="secondary"
      >
        ניתוח מחדש של המשרה
      </Button>
    </div>
  );
};
