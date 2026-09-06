import type { ReactNode } from "react";

import { type ClassValue, cx } from "./cx";
import { type StatusTone, statusPresentation } from "./status";

const toneClasses: Record<StatusTone, string> = {
  success: "border-cv-success/20 border-s-cv-success bg-cv-success-soft/60",
  warning: "border-cv-warning/20 border-s-cv-warning bg-cv-warning-soft/60",
  blocker: "border-cv-blocker/20 border-s-cv-blocker bg-cv-blocker-soft/60",
  progress: "border-cv-accent/20 border-s-cv-accent bg-cv-accent-soft/60",
  neutral: "border-cv-border border-s-cv-text-muted bg-cv-surface-muted",
};

const toneIconClasses: Record<StatusTone, string> = {
  success: "text-cv-success",
  warning: "text-cv-warning",
  blocker: "text-cv-blocker",
  progress: "text-cv-accent",
  neutral: "text-cv-text-muted",
};

interface CalloutProps {
  action?: ReactNode;
  children?: ReactNode;
  className?: ClassValue;
  /* "alert" only when the callout appears in response to a user action. */
  role?: "alert" | "status";
  title: ReactNode;
  tone: StatusTone;
}

/* A.2: a warning states its label and never looks like a blocker; a blocker states its
   reason in plain language and offers the allowed resolution action when one exists. */
export const Callout = ({ action, children, className, role, title, tone }: CalloutProps) => {
  const { icon: Icon, label } = statusPresentation[tone];

  return (
    <div className={cx("rounded-control border border-s-2 px-3.5 py-2.5", toneClasses[tone], className)} role={role}>
      <div className="flex items-start gap-2.5">
        <Icon
          aria-hidden="true"
          className={cx(
            "mt-0.5 size-4 shrink-0",
            toneIconClasses[tone],
            tone === "progress" && "motion-safe:animate-spin",
          )}
        />
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-baseline gap-x-2 gap-y-0.5">
            <span className={cx("text-support font-bold", toneIconClasses[tone])}>{label}</span>
            {/* A.3: the tone label is Hebrew, but a callout usually carries a backend
                title and detail that may be English. dir="auto" lets each run pick its
                own direction instead of being forced into the RTL shell. */}
            <div className="text-support font-semibold leading-6 text-cv-text" dir="auto">
              {title}
            </div>
          </div>
          {children === undefined ? null : (
            <div className="mt-1 text-support leading-6 text-cv-text-muted" dir="auto">
              {children}
            </div>
          )}
          {action === undefined ? null : <div className="mt-2.5">{action}</div>}
        </div>
      </div>
    </div>
  );
};
