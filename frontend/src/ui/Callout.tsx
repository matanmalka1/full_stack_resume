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

/* The banner emphasis trades the compact inline treatment - a thin accent edge, tight
   padding, body text in plain muted grey - for a full-bordered block whose own text is
   tinted in the tone. Reserved for the one verdict a whole screen opens with and is
   organized around; every other Callout on the page stays the quieter inline notice. */
const bannerToneClasses: Record<StatusTone, string> = {
  success: "border-cv-success/30 bg-cv-success-soft",
  warning: "border-cv-warning/30 bg-cv-warning-soft",
  blocker: "border-cv-blocker/30 bg-cv-blocker-soft",
  progress: "border-cv-accent/30 bg-cv-accent-soft",
  neutral: "border-cv-border bg-cv-surface-muted",
};

interface CalloutProps {
  action?: ReactNode;
  children?: ReactNode;
  className?: ClassValue;
  /* Omitted, a Callout stays the compact inline notice it has always been. "banner" is
     for the single screen-level verdict everything below it answers to. */
  emphasis?: "banner";
  /* "alert" only when the callout appears in response to a user action. */
  role?: "alert" | "status";
  title: ReactNode;
  tone: StatusTone;
}

/* A.2: a warning states its label and never looks like a blocker; a blocker states its
   reason in plain language and offers the allowed resolution action when one exists. */
export const Callout = ({ action, children, className, emphasis, role, title, tone }: CalloutProps) => {
  const { icon: Icon, label } = statusPresentation[tone];
  const banner = emphasis === "banner";

  return (
    <div
      className={cx(
        banner ? "rounded-surface border p-4" : "rounded-control border border-s-2 px-3.5 py-2.5",
        banner ? bannerToneClasses[tone] : toneClasses[tone],
        className,
      )}
      role={role}
    >
      <div className={cx("flex items-start", banner ? "gap-3.5" : "gap-2.5")}>
        <Icon
          aria-hidden="true"
          className={cx(
            "mt-0.5 shrink-0",
            banner ? "size-5" : "size-4",
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
            <div
              className={cx(
                "leading-6",
                banner ? cx("text-body font-bold", toneIconClasses[tone]) : "text-support font-semibold text-cv-text",
              )}
              dir="auto"
            >
              {title}
            </div>
          </div>
          {children === undefined ? null : (
            <div
              className={cx("mt-1 text-support leading-6", banner ? toneIconClasses[tone] : "text-cv-text-muted")}
              dir="auto"
            >
              {children}
            </div>
          )}
          {action === undefined ? null : <div className="mt-2.5">{action}</div>}
        </div>
      </div>
    </div>
  );
};
