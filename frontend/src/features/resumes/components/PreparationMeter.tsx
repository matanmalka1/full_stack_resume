import type { ApplicationListItem } from "@/api/contracts";
import { preparationStateLabels } from "@/features/preparation";
import { ProgressSegments } from "@/ui/ProgressSegments";
import { preparationProgress } from "../model/resumePresentation";

/* The CV track on a card: one segment per preparation state, filled to where the
   Application's document stands, and its position in words beside it - "קו״ח 3/5", or
   "מוכן" once there is nothing left to do. It is a position, not a percentage of work: an
   edit to an approved document projects back to `draft_in_progress` and the bar shortens
   with it. The state's own name is what assistive tech hears, rather than a fraction. */
export const PreparationMeter = ({ item }: { item: ApplicationListItem }) => {
  const { step, total } = preparationProgress(item.preparation_state);
  const ready = item.preparation_state === "ready";

  return (
    <span className="flex min-w-0 flex-1 items-center gap-2">
      <ProgressSegments done={step} total={total} />
      <span aria-hidden="true" className="shrink-0 text-caption font-bold text-cv-text-muted tabular-nums">
        {ready ? (
          "מוכן"
        ) : (
          <>
            קו״ח <span dir="ltr">{`${step}/${total}`}</span>
          </>
        )}
      </span>
      <span className="sr-only">
        הכנת קורות החיים: {preparationStateLabels[item.preparation_state]}, שלב {step} מתוך {total}
      </span>
    </span>
  );
};
