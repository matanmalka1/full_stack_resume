import type { LucideIcon } from "lucide-react";
import type { ReactNode } from "react";

import type { ApplicationListItem } from "@/api/contracts";
import { StatusBadge } from "@/ui/StatusBadge";
import { cx } from "@/ui/cx";
import { type Tone, tonePresentation } from "@/ui/tone";
import { confidenceText, fitLevelIcon, fitLevelLabel, fitLevelTone } from "@/features/preparation";
import { recruitmentStatusIcon, recruitmentStatusLabel, recruitmentStatusTone } from "@/features/recruitment";
import { preparationStateIcons, preparationStateLabels, preparationStateTones } from "@/features/preparation";
import type { ApplicationListViewVariant } from "../model/applicationList.types";
import { preparationProgress } from "../model/applicationListPresentation";

const quietToneClasses: Record<Tone, string> = {
  success: "text-cv-success",
  warning: "text-cv-warning",
  blocker: "text-cv-blocker",
  info: "text-cv-info",
  progress: "text-cv-accent",
  neutral: "text-cv-text-muted",
};

const QuietStatus = ({ children, icon, tone }: { children: ReactNode; icon?: LucideIcon; tone: Tone }) => {
  const Icon = icon ?? tonePresentation[tone].icon;

  return (
    <span className={cx("inline-flex items-start gap-1.5 text-support font-medium", quietToneClasses[tone])}>
      <Icon aria-hidden="true" className="mt-0.5 size-icon-md shrink-0" />
      <span className="min-w-0">{children}</span>
    </span>
  );
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

  return (
    <span>
      <QuietStatus icon={fitLevelIcon(item.fit_level)} tone={fitLevelTone(item.fit_level)}>
        {fitScoreLabel == null ? label : `${label} · ${fitScoreLabel}`}
      </QuietStatus>
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

  return (
    <div className="flex flex-col items-start gap-1">
      <QuietStatus
        icon={recruitmentStatusIcon(item.recruitment_status)}
        tone={recruitmentStatusTone(item.recruitment_status)}
      >
        {label}
      </QuietStatus>
      {item.is_closed ? <span className="text-support text-cv-text-muted">התהליך נסגר</span> : null}
    </div>
  );
};

/* Discrete segments rather than a continuous bar: the states are positions, not a
   percentage, and a smooth fill would claim a precision the projection does not have.
   The words under it carry the fact; the segments are decoration for the eye. */
const PreparationSteps = ({ state }: { state: ApplicationListItem["preparation_state"] }) => {
  const { step, total } = preparationProgress(state);

  return (
    <span className="flex w-full max-w-40 flex-col gap-1">
      <span aria-hidden="true" className="grid grid-flow-col auto-cols-fr gap-0.5">
        {Array.from({ length: total }, (_, index) => (
          <span
            className={cx("h-1 rounded-pill", index < step ? "bg-cv-accent" : "bg-cv-border")}
            key={index}
          />
        ))}
      </span>
      <span className="text-support text-cv-text-muted tabular-nums">{`שלב ${step} מתוך ${total}`}</span>
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

  if (variant !== "row") {
    return badge;
  }

  return (
    <span className="flex w-full flex-col items-start gap-1.5">
      {badge}
      <PreparationSteps state={item.preparation_state} />
    </span>
  );
};
