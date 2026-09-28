import { aiRegenerationAvailable } from "@/api/settings";
import type { ApplicationDetail } from "@/api/contracts";
import { Button } from "@/ui/Button";
import { useAnalyzeCommand } from "../../api/mutations";
import type { WorkflowActionPlan } from "../../model/workflowActionPlan";

export const ReanalyzeCard = ({
  detail,
  onQueued,
  operationLive,
  plan,
}: {
  detail: ApplicationDetail;
  onQueued: (operationId: string) => void;
  operationLive: boolean;
  plan: WorkflowActionPlan;
}) => {
  const { analyze, settings } = useAnalyzeCommand(detail, onQueued);

  return (
    <div className="flex flex-col gap-3">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <p className="max-w-md text-support leading-6 text-cv-text-muted">
          {plan.draftWouldReplace
            ? "ניתוח מחדש יוצר ניתוח חדש ונפרד לאותו תצלום משרה. הטיוטה הפעילה נשמרת כפי שהיא, אך תסומן כלא מעודכנת מולו."
            : "ניתוח מחדש כדאי רק אם הסיווג שלמעלה נראה שגוי. הוא יוצר ניתוח חדש ונפרד לאותו תצלום משרה, ואינו מושך נוסח משרה מעודכן."}{" "}
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
