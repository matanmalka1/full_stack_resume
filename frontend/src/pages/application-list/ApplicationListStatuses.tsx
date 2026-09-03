import type { LucideIcon } from "lucide-react";
import type { ReactNode } from "react";

import type { ApplicationListItem } from "../../api/contracts";
import { StatusBadge } from "../../ui/StatusBadge";
import { cx } from "../../ui/cx";
import { type StatusTone, statusPresentation } from "../../ui/status";
import { fitLevelIcon, fitLevelLabel, fitLevelTone } from "../application/analysisLabels";
import { recruitmentStatusIcon, recruitmentStatusLabel, recruitmentStatusTone } from "../application/applicationLabels";
import type { ApplicationListViewVariant } from "./ApplicationListParts";

const quietToneClasses: Record<StatusTone, string> = {
  success: "text-cv-success",
  warning: "text-cv-warning",
  blocker: "text-cv-blocker",
  progress: "text-cv-accent",
  neutral: "text-cv-text-muted",
};

const QuietStatus = ({ children, icon, tone }: { children: ReactNode; icon?: LucideIcon; tone: StatusTone }) => {
  const Icon = icon ?? statusPresentation[tone].icon;

  return (
    <span className={cx("inline-flex items-start gap-1.5 text-support font-medium", quietToneClasses[tone])}>
      <Icon aria-hidden="true" className="mt-0.5 size-4 shrink-0" />
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
  if (variant === "card") {
    return (
      <StatusBadge
        className="shrink-0 px-2 py-0.5"
        icon={fitLevelIcon(item.fit_level)}
        tone={fitLevelTone(item.fit_level)}
      >
        {label}
      </StatusBadge>
    );
  }

  if (variant === "pipeline") {
    return <span className="shrink-0 text-support font-semibold text-cv-accent">{label}</span>;
  }

  const confidence =
    item.classification_confidence == null
      ? undefined
      : `רמת הביטחון של הסיווג: ${Math.round(item.classification_confidence * 100)}%`;

  return (
    <span title={confidence}>
      <QuietStatus icon={fitLevelIcon(item.fit_level)} tone={fitLevelTone(item.fit_level)}>
        {label}
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
