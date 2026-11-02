import { Archive } from "lucide-react";

import type { ApplicationListItem } from "@/api/contracts";
import { preparationStateLabels } from "@/features/preparation";
import { recruitmentStatusLabel } from "@/features/recruitment";
import { ProgressSegments } from "@/ui/ProgressSegments";
import { StatusBadge } from "@/ui/StatusBadge";
import { cx } from "@/ui/cx";
import { preparationProgress } from "../model/applicationListPresentation";
import { recruitmentStageOf } from "../model/recruitmentStages";

/* The employer's side of an Application as the board names it: its recruitment stage, on a
   chip whose weight says how far along it is. A closed Application has no stage, so its
   chip is the exact status word in a quiet outline.

   The design draws the stage's mark inside the chip on a phone only, where the chip leads
   the card's second line; `phoneIcon` asks for that. The tone is "progress" for its dark
   text on the soft fill - the mark is always the stage's own, so nothing spins. */
export const ApplicationStageBadge = ({
  className,
  item,
  phoneIcon = false,
}: {
  className?: string;
  item: ApplicationListItem;
  phoneIcon?: boolean;
}) => {
  const stage = recruitmentStageOf(item.recruitment_status);

  return (
    <StatusBadge
      className={cx(phoneIcon ? "lg:[&>svg]:hidden" : "[&>svg]:hidden", className)}
      icon={stage?.icon ?? Archive}
      tone="progress"
      variant={stage?.badge ?? "outline"}
    >
      {stage?.label ?? recruitmentStatusLabel(item.recruitment_status)}
    </StatusBadge>
  );
};

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
