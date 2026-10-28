import { CircleHelp } from "lucide-react";

import type { ApplicationListItem } from "@/api/contracts";
import { StatusBadge } from "@/ui/StatusBadge";
import { Tooltip } from "@/ui/Tooltip";
import { cx } from "@/ui/cx";
import { toneDotClasses } from "@/ui/tone";
import { confidenceText, fitLevelLabel } from "@/features/preparation";
import { recruitmentStatusLabel, recruitmentStatusTone } from "@/features/recruitment";
import { preparationStateIcons, preparationStateLabels, preparationStateTones } from "@/features/preparation";
import type { ApplicationListViewVariant } from "../model/applicationList.types";
import { preparationProgress } from "../model/applicationListPresentation";
import { ApplicationRunningOperation } from "./ApplicationCardNextAction";

/* One shape for every fit chip, score or mark, so the cards' headers line up. */
const fitChipClasses =
  "inline-flex h-7 min-w-12 items-center justify-center rounded-control bg-cv-surface-muted px-2.5 text-support font-bold";

/* Fit as the board says it: the score where there is one, the level word where there
   is not. */
const fitScoreText = (item: ApplicationListItem): string | null =>
  item.fit_score == null ? null : confidenceText(item.fit_score);

/* One chip, as the details dialog shows fit. The level is never lost - it is the
   chip's tooltip, which is in the document and so is read with it. */
export const ApplicationFitStatus = ({ item }: { item: ApplicationListItem }) => {
  if (item.fit_level == null) {
    return (
      <Tooltip align="center" label="המשרה טרם נותחה">
        <span className="text-support text-cv-text-muted">—</span>
      </Tooltip>
    );
  }

  const label = fitLevelLabel(item.fit_level);
  const score = fitScoreText(item);

  /* An unchecked fit has no score and a sentence for a level; the chip draws a mark and
     leaves the sentence to the tooltip. */
  if (score == null && item.fit_level === "unknown") {
    return (
      <Tooltip align="center" label={label}>
        <span className={cx(fitChipClasses, "text-cv-text-muted")}>
          <CircleHelp aria-hidden="true" className="size-4" />
        </span>
      </Tooltip>
    );
  }

  return (
    <Tooltip align="center" label={label}>
      <span className={cx(fitChipClasses, "text-cv-text tabular-nums")}>{score ?? label}</span>
    </Tooltip>
  );
};

/* The employer's side as one outlined pill under the CV track: a status, not a step,
   so it is drawn as a tag rather than a bar. */
export const ApplicationRecruitmentStatus = ({ item }: { item: ApplicationListItem }) => (
  <span
    className={cx(
      "inline-flex items-center gap-1.5 rounded-pill border px-2 py-0.5 text-support font-medium",
      item.is_closed ? "border-cv-border text-cv-text-muted" : "border-cv-border-strong text-cv-text",
    )}
  >
    <span
      aria-hidden="true"
      className={cx("size-1.5 shrink-0 rounded-pill", toneDotClasses[recruitmentStatusTone(item.recruitment_status)])}
    />
    {recruitmentStatusLabel(item.recruitment_status)}
  </span>
);

/* The CV track as one line of a card: a bar of one segment per state, then the position.
   The bar is a position among the five states, not a percentage of work - an edit to an
   approved document projects back to `draft_in_progress` and the bar shortens with it.
   The state's name is the progress element's own label, which assistive tech reads; the
   eye reads the bar and the position. */
const PreparationTrack = ({ state }: { state: ApplicationListItem["preparation_state"] }) => {
  const { step, total } = preparationProgress(state);
  const label = preparationStateLabels[state];

  return (
    <span className="flex min-w-0 flex-1 flex-row-reverse items-center gap-2">
      <span className="shrink-0 text-support font-bold text-cv-text-muted tabular-nums">
        קו״ח <span dir="ltr">{`${step}/${total}`}</span>
      </span>
      <progress
        aria-label={`הכנת קורות החיים: ${label}`}
        aria-valuetext={`שלב ${step} מתוך ${total}`}
        className="sr-only"
        max={total}
        value={step}
      />
      <span aria-hidden="true" className="grid min-w-0 flex-1 auto-cols-fr grid-flow-col gap-0.75">
        {Array.from({ length: total }, (_, index) => (
          <span className={cx("h-1.5 rounded-pill", index < step ? "bg-cv-accent" : "bg-cv-border")} key={index} />
        ))}
      </span>
    </span>
  );
};

/* "card" is the labelled track the cards draw; "pipeline" is the compact
   badge the global search palette shows beside a result. */
export const ApplicationPreparationStatus = ({
  item,
  variant,
}: {
  item: ApplicationListItem;
  variant: ApplicationListViewVariant;
}) =>
  variant === "card" ? (
    <PreparationTrack state={item.preparation_state} />
  ) : (
    <StatusBadge
      className="px-2 py-0.5"
      icon={preparationStateIcons[item.preparation_state]}
      tone={preparationStateTones[item.preparation_state]}
    >
      {preparationStateLabels[item.preparation_state]}
    </StatusBadge>
  );

/* The progress line the card draws: the employer's status leading, with any run still
   going beside it, then the CV track. */
export const ApplicationProgress = ({ item }: { item: ApplicationListItem }) => (
  <div className="flex w-full flex-row-reverse items-center gap-2.5">
    <ApplicationPreparationStatus item={item} variant="card" />
    <div className="flex shrink-0 items-center gap-1.5">
      <ApplicationRecruitmentStatus item={item} />
      <ApplicationRunningOperation item={item} />
    </div>
  </div>
);
