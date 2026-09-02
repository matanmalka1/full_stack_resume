import { Archive, Award, Bookmark, PhoneCall, Send, Users, type LucideIcon } from "lucide-react";

import type { RecruitmentStatus } from "../../api/contracts";

export type RecruitmentStageTone = "neutral" | "accent" | "warning" | "success";

interface RecruitmentStageShape {
  id: string;
  label: string;
  statuses: readonly RecruitmentStatus[];
  icon: LucideIcon;
  tone: RecruitmentStageTone;
}

/* Single source for "which recruitment stage does this status belong to": the filter
   bar and the pipeline board used to answer this differently, so the same application
   could sit in different columns depending on which screen was open. assignment groups
   with interviews and final_stage groups with offer/accepted - a product decision, not
   a default either screen is free to redraw locally. */
export const recruitmentStages = [
  { id: "saved", label: "נשמר", statuses: ["saved"], icon: Bookmark, tone: "neutral" },
  { id: "applied", label: "הוגש", statuses: ["applied"], icon: Send, tone: "accent" },
  { id: "screening", label: "סינון טלפוני", statuses: ["recruiter_screen"], icon: PhoneCall, tone: "warning" },
  {
    id: "interviews",
    label: "ראיונות ומטלות",
    statuses: ["interview", "assignment"],
    icon: Users,
    tone: "success",
  },
  {
    id: "offer",
    label: "שלב סופי והצעה",
    statuses: ["final_stage", "offer", "accepted"],
    icon: Award,
    tone: "success",
  },
] as const satisfies readonly RecruitmentStageShape[];

/* Not one of the active stages a filter click can select - a closed application has left
   the pipeline rather than reached a further stage of it. Shown only by views that also
   render closed applications alongside the active ones. */
export const closedStage = {
  id: "closed",
  label: "תהליכים סגורים",
  statuses: ["rejected", "withdrawn", "closed"],
  icon: Archive,
  tone: "neutral",
} as const satisfies RecruitmentStageShape;

export type RecruitmentStageId = (typeof recruitmentStages)[number]["id"];

export const selectedStage = (statuses: readonly RecruitmentStatus[] | undefined): RecruitmentStageId | null => {
  if (statuses == null || statuses.length === 0) {
    return null;
  }

  return (
    recruitmentStages.find((stage) =>
      statuses.every((status) => (stage.statuses as readonly RecruitmentStatus[]).includes(status)),
    )?.id ?? null
  );
};
