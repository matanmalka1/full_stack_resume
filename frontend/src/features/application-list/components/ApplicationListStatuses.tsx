import type { ApplicationListItem } from "@/api/contracts";
import { StatusBadge } from "@/ui/StatusBadge";
import { cx } from "@/ui/cx";
import type { Tone } from "@/ui/tone";
import { confidenceText, fitLevelIcon, fitLevelLabel, fitLevelTone } from "@/features/preparation";
import { recruitmentStatusLabel, recruitmentStatusTone } from "@/features/recruitment";
import { preparationStateIcons, preparationStateLabels, preparationStateTones } from "@/features/preparation";
import type { ApplicationListViewVariant } from "../model/applicationList.types";
import { preparationProgress } from "../model/applicationListPresentation";

const quietDotClasses: Record<Tone, string> = {
  success: "bg-cv-success",
  warning: "bg-cv-warning",
  blocker: "bg-cv-blocker",
  info: "bg-cv-info",
  progress: "bg-cv-accent",
  neutral: "bg-cv-text-muted",
};

export const ApplicationFitStatus = ({
  item,
  variant,
}: {
  item: ApplicationListItem;
  variant: ApplicationListViewVariant;
}) => {
  if (item.fit_level == null) {
    return variant === "row" ? (
      <span className="text-support text-cv-text-muted" title="המשרה טרם נותחה">
        —
      </span>
    ) : null;
  }

  const label = fitLevelLabel(item.fit_level);
  // Fit is projected from the analysis's requirements when the list is built. There is
  // no classification confidence to show beside it.
  const fitScoreLabel = item.fit_score == null ? null : confidenceText(item.fit_score);

  if (variant === "card") {
    return (
      <span>
        <StatusBadge
          className="shrink-0 px-2 py-0.5"
          icon={fitLevelIcon(item.fit_level)}
          tone={fitLevelTone(item.fit_level)}
        >
          {fitScoreLabel == null ? label : `${label} · ${fitScoreLabel}`}
        </StatusBadge>
      </span>
    );
  }

  if (variant === "pipeline") {
    return <span className="shrink-0 text-support font-semibold text-cv-accent">{label}</span>;
  }

  /* The row draws fit as one chip, the way the table's other number columns read: the
     score where there is one, the level word where there is not. The level is never
     lost - it is the chip's title and, beside a score, its spoken name. */
  return (
    <span
      className="inline-flex min-w-12 items-center justify-center rounded-control bg-cv-surface-muted px-2.5 py-1 text-support font-bold text-cv-text tabular-nums"
      title={label}
    >
      {fitScoreLabel ?? label}
      {fitScoreLabel == null ? null : <span className="sr-only"> · {label}</span>}
    </span>
  );
};

export const ApplicationRecruitmentStatus = ({
  item,
  variant,
}: {
  item: ApplicationListItem;
  variant: ApplicationListViewVariant;
}) => {
  const label = recruitmentStatusLabel(item.recruitment_status);

  if (variant === "card") {
    return (
      <StatusBadge className="px-2.5 py-0.5" tone="neutral">
        {label}
      </StatusBadge>
    );
  }

  if (variant === "pipeline") {
    return <span className="text-cv-text-muted">{label}</span>;
  }

  /* In the row the employer's side is one outlined pill under the CV track: a status,
     not a step, so it is drawn as a tag rather than a bar. */
  return (
    <span
      className={cx(
        "inline-flex items-center gap-1.5 rounded-pill border px-2 py-0.5 text-support font-medium",
        item.is_closed ? "border-cv-border text-cv-text-muted" : "border-cv-border-strong text-cv-text",
      )}
    >
      <span aria-hidden="true" className={cx("size-1.5 shrink-0 rounded-pill", quietDotClasses[recruitmentStatusTone(item.recruitment_status)])} />
      {label}
    </span>
  );
};

/* The row's CV track, drawn after demo_re: the state named on one line with its
   position at the far end, and one bar under it filled to that position. The bar is a
   position among the seven states, not a percentage of work - a stale draft that needs a
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
      <span
        aria-label={`הכנת קורות החיים: ${label}`}
        aria-valuemax={total}
        aria-valuemin={1}
        aria-valuenow={step}
        aria-valuetext={`שלב ${step} מתוך ${total}`}
        className="flex h-1.5 w-full overflow-hidden rounded-pill bg-cv-surface-muted"
        role="progressbar"
      >
        <span className="h-full rounded-pill bg-cv-accent" style={{ width: `${(step / total) * 100}%` }} />
      </span>
    </span>
  );
};

export const ApplicationPreparationStatus = ({
  item,
  variant,
}: {
  item: ApplicationListItem;
  variant: ApplicationListViewVariant;
}) => {
  const badge = (
    <StatusBadge
      className={variant === "row" ? "gap-1.5 px-2.5 text-start" : variant === "card" ? "px-2.5 py-0.5" : "px-2 py-0.5"}
      icon={preparationStateIcons[item.preparation_state]}
      tone={preparationStateTones[item.preparation_state]}
    >
      {preparationStateLabels[item.preparation_state]}
    </StatusBadge>
  );

  return variant === "row" ? <PreparationTrack state={item.preparation_state} /> : badge;
};
