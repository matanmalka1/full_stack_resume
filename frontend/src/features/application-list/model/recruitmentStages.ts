import { Award, Bookmark, PhoneCall, Send, Users, type LucideIcon } from "lucide-react";

import type { RecruitmentStatus } from "@/api/contracts";
import type { BadgeVariant } from "@/ui/StatusBadge";

interface RecruitmentStageShape {
  id: string;
  label: string;
  statuses: readonly RecruitmentStatus[];
  icon: LucideIcon;
  /* How loud the stage's chip draws on a card: a stage not yet started is an outline, one
     under way a soft fill, and the stages where the employer is talking to the reader the
     solid accent - the cards that matter most this week stand out in a column of them. */
  badge: BadgeVariant;
}

/* Single source for "which recruitment stage does this status belong to": the cards'
   chips and the stages view's columns answer it from here, so the same Application cannot
   sit under different names depending on which view is open. assignment groups with
   interviews and final_stage groups with offer/accepted - a product decision, not a
   default either view is free to redraw locally. */
export const recruitmentStages = [
  { id: "saved", label: "טרם הוגש", statuses: ["saved"], icon: Bookmark, badge: "outline" },
  { id: "applied", label: "הוגשה מועמדות", statuses: ["applied"], icon: Send, badge: "soft" },
  { id: "screening", label: "סינון טלפוני / HR", statuses: ["recruiter_screen"], icon: PhoneCall, badge: "soft" },
  { id: "interviews", label: "ראיונות ומטלות", statuses: ["interview", "assignment"], icon: Users, badge: "solid" },
  {
    id: "offer",
    label: "שלב סופי והצעה",
    statuses: ["final_stage", "offer", "accepted"],
    icon: Award,
    badge: "solid",
  },
] as const satisfies readonly RecruitmentStageShape[];

export type RecruitmentStage = (typeof recruitmentStages)[number];

/* The active stage a status belongs to, or null for a closed one - a closed Application
   has left the pipeline rather than reached a further stage of it. */
export const recruitmentStageOf = (status: string): RecruitmentStage | null =>
  recruitmentStages.find((stage) => (stage.statuses as readonly string[]).includes(status)) ?? null;
