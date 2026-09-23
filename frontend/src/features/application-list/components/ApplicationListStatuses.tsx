import type { ApplicationListItem } from "@/api/contracts";
import { StatusBadge } from "@/ui/StatusBadge";
import { Tooltip } from "@/ui/Tooltip";
import { cx } from "@/ui/cx";
import type { Tone } from "@/ui/tone";
import { confidenceText, fitLevelLabel } from "@/features/preparation";
import { recruitmentStatusLabel, recruitmentStatusTone } from "@/features/recruitment";
import { preparationStateIcons, preparationStateLabels, preparationStateTones } from "@/features/preparation";
import type { ApplicationListViewVariant } from "../model/applicationList.types";
import { preparationProgress } from "../model/applicationListPresentation";
import { ApplicationRunningOperation } from "./ApplicationRowNextAction";

const quietDotClasses: Record<Tone, string> = {
  success: "bg-cv-success",
  warning: "bg-cv-warning",
  blocker: "bg-cv-blocker",
  info: "bg-cv-info",
  progress: "bg-cv-accent",
  neutral: "bg-cv-text-muted",
};

/* Fit as the board says it: the score where there is one, the level word where there
   is not. `fitScoreText` is shared by the table's chip and the card's footer. */
export const fitScoreText = (item: ApplicationListItem): string | null =>
  item.fit_score == null ? null : confidenceText(item.fit_score);

/* One chip, the way demo_re's score column reads. The level is never lost - it is the
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

  return (
    <Tooltip align="center" label={label}>
      <span className="inline-flex min-w-12 items-center justify-center rounded-control bg-cv-surface-muted px-2.5 py-1 text-support font-bold text-cv-text tabular-nums">
        {score ?? label}
      </span>
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
      className={cx("size-1.5 shrink-0 rounded-pill", quietDotClasses[recruitmentStatusTone(item.recruitment_status)])}
    />
    {recruitmentStatusLabel(item.recruitment_status)}
  </span>
);

/* The CV track, drawn after demo_re: the state named on one line with its position at
   the far end, and one bar under it filled to that position. The bar is a position
   among the seven states, not a percentage of work - a stale draft that needs a
   decision projects back to `needs_review` and the bar shortens with it. */
const PreparationTrack = ({ state }: { state: ApplicationListItem["preparation_state"] }) => {
  const { step, total } = preparationProgress(state);
  const label = preparationStateLabels[state];

  return (
    <span className="flex w-full flex-col gap-1">
      <span className="flex items-baseline justify-between gap-2 text-support">
        <span className="min-w-0 font-medium text-cv-text">
          <span className="text-cv-text-muted">הכנת קו״ח: </span>
          <span>{label}</span>
        </span>
        <span className="shrink-0 text-cv-text-muted tabular-nums" dir="ltr">{`${step}/${total}`}</span>
      </span>
      <progress
        aria-label={`הכנת קורות החיים: ${label}`}
        aria-valuetext={`שלב ${step} מתוך ${total}`}
        className="sr-only"
        max={total}
        value={step}
      />
      <span aria-hidden="true" className="flex h-1.5 w-full overflow-hidden rounded-pill bg-cv-surface-muted">
        <span className="h-full rounded-pill bg-cv-accent" style={{ width: `${(step / total) * 100}%` }} />
      </span>
    </span>
  );
};

/* "row" is the labelled track the table and the cards draw; "pipeline" is the compact
   badge the global search palette shows beside a result. */
export const ApplicationPreparationStatus = ({
  item,
  variant,
}: {
  item: ApplicationListItem;
  variant: ApplicationListViewVariant;
}) =>
  variant === "row" ? (
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

/* The progress block shared by the table row and the card: the CV track, and under it
   the employer's status with any run still going beside it. */
export const ApplicationProgress = ({ item }: { item: ApplicationListItem }) => (
  <div className="flex w-full flex-col items-start gap-2">
    <ApplicationPreparationStatus item={item} variant="row" />
    <div className="flex flex-wrap items-center gap-1.5">
      <ApplicationRecruitmentStatus item={item} />
      <ApplicationRunningOperation item={item} />
    </div>
  </div>
);
