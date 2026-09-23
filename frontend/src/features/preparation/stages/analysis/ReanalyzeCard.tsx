import { aiRegenerationAvailable } from "@/api/settings";
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
  operationLive,
  plan,
}: {
  detail: ApplicationDetail;
  onQueued: (operationId: string) => void;
  /* Whether this Application's work is under way, by `isOperationLive`: the actions that
     change what a run replaces wait for it, whether or not its overlay is showing. */
  operationLive: boolean;
  plan: WorkflowActionPlan;
}) => {
  const { analyze, settings } = useAnalyzeCommand(detail, onQueued);

  if (plan.analyze === null || !plan.analyze.reanalysis) {
    return null;
  }

  return (
    <div className="flex flex-col gap-3">
      {/* No rule of its own: the panel's `divide-y` draws the one above it, in the same
         rhythm as every finding it follows. */}
      <div className="flex flex-wrap items-center justify-between gap-4">
        <p className="max-w-md text-support leading-6 text-cv-text-muted">
          {plan.draftWouldReplace
            ? "ניתוח מחדש יוצר ניתוח חדש ונפרד לאותו תצלום משרה. הטיוטה הפעילה נשמרת כפי שהיא, אך תסומן כלא מעודכנת מולו."
            : "ניתוח מחדש כדאי רק אם הסיווג שלמעלה נראה שגוי. הוא יוצר ניתוח חדש ונפרד לאותו תצלום משרה, ואינו מושך נוסח משרה מעודכן."}{" "}
          {/* Same cost sentence as the first-analysis note in `WorkflowActions`, read from
              the same `analyzeProvider` value `analyze.mutate()` is about to send - the
              switch below folded in - so a re-analysis names its lane before the press
              exactly like the first one does. */}
          {settings === undefined
            ? null
            : aiRegenerationAvailable(settings)
              ? "ניתוח מחדש זה יכלול קריאת AI בתשלום."
              : "כדי לנתח מחדש יש להגדיר ולהפעיל ספק AI."}
        </p>
        <Button
          disabled={operationLive || settings === undefined || !aiRegenerationAvailable(settings)}
          onClick={() => analyze.mutate()}
          pending={analyze.isPending}
          pendingLabel="מפעיל ניתוח…"
          variant="secondary"
        >
          ניתוח מחדש של המשרה
        </Button>
      </div>
    </div>
  );
};
