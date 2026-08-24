import { CircleCheck, Info, LoaderCircle, OctagonAlert, TriangleAlert } from "lucide-react";
import type { LucideIcon } from "lucide-react";

/* A.2: status is text label + icon + position. Color is never the only signal, so every
   tone carries both an icon and a Hebrew label here rather than in each call site. */
export type StatusTone = "success" | "warning" | "blocker" | "progress" | "neutral";

interface StatusPresentation {
  icon: LucideIcon;
  label: string;
}

export const statusPresentation: Record<StatusTone, StatusPresentation> = {
  success: { icon: CircleCheck, label: "הושלם" },
  warning: { icon: TriangleAlert, label: "אזהרה" },
  blocker: { icon: OctagonAlert, label: "חסימה" },
  progress: { icon: LoaderCircle, label: "בתהליך" },
  neutral: { icon: Info, label: "מידע" },
};
