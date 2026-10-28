import type { LucideIcon } from "lucide-react";
import type { ReactNode } from "react";

import { type ClassValue, cx } from "./cx";
import { type Tone, tonePresentation, toneBackgroundClasses, toneTextClasses } from "./tone";

/* How loud the chip draws, independent of its tone. "soft" is the design's default
   chip - a tinted fill and no edge. "solid" fills it with the accent, for the one chip on
   a card that asks for the reader (the board's waiting-on-you stage, a fact awaiting
   approval). "outline" is a quiet edge with no fill, for a state not yet started. */
export type BadgeVariant = "soft" | "solid" | "outline";

const variantClasses = (variant: BadgeVariant, tone: Tone): string => {
  switch (variant) {
    case "solid":
      return "border-cv-accent bg-cv-accent text-cv-on-accent";
    case "outline":
      return `border-cv-border-strong bg-transparent ${toneTextClasses[tone]}`;
    default:
      return `border-transparent ${toneBackgroundClasses[tone]} ${toneTextClasses[tone]}`;
  }
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
  variant?: BadgeVariant;
}

export const StatusBadge = ({ children, className, icon, tone, variant = "soft" }: StatusBadgeProps) => {
  const { icon: toneIcon, label } = tonePresentation[tone];
  const Icon = icon ?? toneIcon;

  return (
    <span
      className={cx(
        "inline-flex shrink-0 items-center gap-1.5 rounded-pill border px-2.5 py-1 text-caption font-bold",
        variantClasses(variant, tone),
        className,
      )}
    >
      {/* Only the tone's own loader spins. An overridden icon is a static mark for a
          state that happens to be tinted like live work - a spinning telephone would
          claim the row was working when it is not. */}
      <Icon
        aria-hidden="true"
        className={cx("size-3.5 shrink-0", icon === undefined && tone === "progress" && "animate-spin")}
      />
      {children ?? label}
    </span>
  );
};
