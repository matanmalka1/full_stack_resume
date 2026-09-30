import { CircleCheck, Info, LoaderCircle, OctagonAlert, TriangleAlert } from "lucide-react";
import type { LucideIcon } from "lucide-react";

/* The five severities the interface draws, and nothing about what is being described.

   `ui` owns how loud a thing is - success, warning, blocker, progress, neutral - and
   never which domain value maps to which: a preparation state, a recruitment status or
   an analysis fit is named and toned by the feature that owns it, and arrives here
   already reduced to one of these five.

   A.2: a tone is text label + icon + position, never colour alone, so each carries both
   an icon and a Hebrew severity word here rather than in each call site. */
export type Tone = "success" | "warning" | "blocker" | "info" | "progress" | "neutral";

interface TonePresentation {
  icon: LucideIcon;
  label: string;
}

export const tonePresentation: Record<Tone, TonePresentation> = {
  success: { icon: CircleCheck, label: "הושלם" },
  warning: { icon: TriangleAlert, label: "אזהרה" },
  blocker: { icon: OctagonAlert, label: "חסימה" },
  info: { icon: Info, label: "מידע" },
  progress: { icon: LoaderCircle, label: "בתהליך" },
  neutral: { icon: Info, label: "הערה" },
};

/* How loud each tone draws, as class data rather than as a component, so a feature that
   needs a tinted mark of its own - a timeline dot, a chip, a row mark - takes the tone's
   colours from here instead of spelling out a sixth copy of the same table. Each map is one
   property; a caller combines what its element draws. */
export const toneTextClasses: Record<Tone, string> = {
  success: "text-cv-success",
  warning: "text-cv-warning",
  blocker: "text-cv-blocker",
  info: "text-cv-info",
  progress: "text-cv-accent",
  neutral: "text-cv-text-muted",
};

export const toneBorderClasses: Record<Tone, string> = {
  success: "border-cv-success/30",
  warning: "border-cv-warning/30",
  blocker: "border-cv-blocker/30",
  info: "border-cv-info/30",
  progress: "border-cv-accent/30",
  neutral: "border-cv-border",
};

export const toneBackgroundClasses: Record<Tone, string> = {
  success: "bg-cv-success-soft",
  warning: "bg-cv-warning-soft",
  blocker: "bg-cv-blocker-soft",
  info: "bg-cv-info-soft",
  progress: "bg-cv-accent-soft",
  neutral: "bg-cv-surface-muted",
};

/* A solid swatch: the small dot that stands for a tone beside a word. */
export const toneDotClasses: Record<Tone, string> = {
  success: "bg-cv-success",
  warning: "bg-cv-warning",
  blocker: "bg-cv-blocker",
  info: "bg-cv-info",
  progress: "bg-cv-accent",
  neutral: "bg-cv-text-muted",
};

/* The soft tinted treatment a badge or a marker draws: tinted edge, tinted fill, toned text. */
export const toneSoftClasses = (tone: Tone): string =>
  `${toneBorderClasses[tone]} ${toneBackgroundClasses[tone]} ${toneTextClasses[tone]}`;
