import type { ReactNode } from "react";

import { type ClassValue, cx } from "./cx";
import { type StatusTone, statusPresentation } from "./status";

const toneClasses: Record<StatusTone, string> = {
  success: "border-cv-success/30 bg-cv-success/5",
  warning: "border-cv-warning/30 bg-cv-warning/5",
  blocker: "border-cv-blocker/30 bg-cv-blocker/5",
  progress: "border-cv-accent/30 bg-cv-accent-soft",
  neutral: "border-cv-border bg-cv-surface-muted",
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
    <div
      className={cx("rounded-surface border p-4", toneClasses[tone], className)}
      role={role}
    >
      <div className="flex gap-3">
        <Icon aria-hidden="true" className={cx("mt-0.5 size-5 shrink-0", toneIconClasses[tone])} />
        <div className="min-w-0 flex-1">
          <p className="text-support leading-6">
            <span className={cx("font-semibold", toneIconClasses[tone])}>{label}</span>{" "}
            {/* A.3: the tone label is Hebrew, but a callout usually carries a backend
                title and detail that may be English. dir="auto" lets each run pick its
                own direction instead of being forced into the RTL shell. */}
            <span className="text-cv-text" dir="auto">
              {title}
            </span>
          </p>
          {children === undefined ? null : (
            <div className="mt-2 text-support leading-6 text-cv-text" dir="auto">
              {children}
            </div>
          )}
          {action === undefined ? null : <div className="mt-3">{action}</div>}
        </div>
      </div>
    </div>
  );
};
