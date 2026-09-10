import type { LucideIcon } from "lucide-react";
import type { ReactNode } from "react";

import { type ClassValue, cx } from "./cx";
import { type Tone, tonePresentation } from "./tone";

const toneClasses: Record<Tone, string> = {
  success: "border-cv-success/30 bg-cv-success-soft text-cv-success",
  warning: "border-cv-warning/30 bg-cv-warning-soft text-cv-warning",
  blocker: "border-cv-blocker/30 bg-cv-blocker-soft text-cv-blocker",
  info: "border-cv-info/30 bg-cv-info-soft text-cv-info",
  progress: "border-cv-accent/30 bg-cv-accent-soft text-cv-accent",
  neutral: "border-cv-border bg-cv-surface-muted text-cv-text-muted",
};

interface StatusBadgeProps {
  children?: ReactNode;
  className?: ClassValue;
  /* A more specific mark than the tone's own. The tone says how loud the badge is -
     four of them across the whole app - while a closed set like the recruitment axis
     has a face per member. A.2 is unaffected either way: the badge still carries its
     Hebrew word, and the icon repeats what the word says rather than replacing it. */
  icon?: LucideIcon;
  tone: Tone;
}

export const StatusBadge = ({ children, className, icon, tone }: StatusBadgeProps) => {
  const { icon: toneIcon, label } = tonePresentation[tone];
  const Icon = icon ?? toneIcon;

  return (
    <span
      className={cx(
        "inline-flex items-center gap-2 rounded-pill border px-3 py-1 text-support font-semibold",
        toneClasses[tone],
        className,
      )}
    >
      {/* Only the tone's own loader spins. An overridden icon is a static mark for a
          state that happens to be tinted like live work - a spinning telephone would
          claim the row was working when it is not. */}
      <Icon
        aria-hidden="true"
        className={cx("size-icon-md shrink-0", icon === undefined && tone === "progress" && "animate-spin")}
      />
      {children ?? label}
    </span>
  );
};
