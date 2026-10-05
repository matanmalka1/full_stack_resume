import { aiAvailability } from "@/api/settings";
import type { ApplicationDetail } from "@/api/contracts";
import { Button } from "@/ui/Button";
import { useAnalyzeCommand } from "../../api/mutations";

export const ReanalyzeCard = ({
  detail,
  onQueued,
  operationLive,
}: {
  detail: ApplicationDetail;
  onQueued: (operationId: string) => void;
  operationLive: boolean;
}) => {
  const { analyze, settings } = useAnalyzeCommand(detail, onQueued);
  const ai = aiAvailability(settings);

  return (
    <div className="flex flex-col gap-3">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <p className="max-w-md text-support leading-6 text-cv-text-muted">
          יוצר ניתוח חדש לאותו נוסח משרה.
          {detail.document_id != null ? " המסמך נשאר על הניתוח הנוכחי עד שתבנו אותו מחדש." : null}{" "}
          {ai === "loading"
            ? null
            : ai === "available"
              ? "ניתוח מחדש זה יכלול קריאת AI בתשלום."
              : "כדי לנתח מחדש יש להגדיר ולהפעיל ספק AI."}
        </p>
        <Button
          disabled={operationLive || ai !== "available"}
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
