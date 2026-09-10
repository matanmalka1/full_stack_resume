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
