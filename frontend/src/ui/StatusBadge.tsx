import type { ReactNode } from "react";

import { type ClassValue, cx } from "./cx";
import { type StatusTone, statusPresentation } from "./status";

const toneClasses: Record<StatusTone, string> = {
  success: "border-cv-success/30 bg-cv-success/10 text-cv-success",
  warning: "border-cv-warning/30 bg-cv-warning/10 text-cv-warning",
  blocker: "border-cv-blocker/30 bg-cv-blocker/10 text-cv-blocker",
  progress: "border-cv-accent/30 bg-cv-accent-soft text-cv-accent",
  neutral: "border-cv-border bg-cv-surface-muted text-cv-text-muted",
};

interface StatusBadgeProps {
  children?: ReactNode;
  className?: ClassValue;
  tone: StatusTone;
}

export const StatusBadge = ({ children, className, tone }: StatusBadgeProps) => {
  const { icon: Icon, label } = statusPresentation[tone];

  return (
    <span
      className={cx(
        "inline-flex items-center gap-2 rounded-pill border px-3 py-1 text-support font-semibold",
        toneClasses[tone],
        className,
      )}
    >
      <Icon
        aria-hidden="true"
        className={cx("size-4 shrink-0", tone === "progress" && "animate-spin")}
      />
      {children ?? label}
    </span>
  );
};
