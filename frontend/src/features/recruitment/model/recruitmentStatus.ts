import {
  Archive,
  BadgeCheck,
  CircleCheck,
  CircleSlash,
  CircleX,
  ClipboardList,
  Clock,
  PhoneCall,
  Send,
  Trophy,
  UserRound,
  type LucideIcon,
} from "lucide-react";

import type { RecruitmentStatus } from "@/api/contracts";
import type { Tone } from "@/ui/tone";

/* Worded after the demo_re board where it names the same status; the statuses it has
   no counterpart for keep their own words. The values are the API's and do not change. */
export const recruitmentStatusLabels: Record<RecruitmentStatus, string> = {
  saved: "טרם הוגש",
  applied: "הוגשה מועמדות",
  recruiter_screen: "סינון טלפוני / HR",
  interview: "תהליך ראיונות",
  assignment: "משימה",
  final_stage: "שלב סופי",
  offer: "התקבלה הצעת שכר",
  accepted: "התקבל",
  rejected: "לא התקבל",
  withdrawn: "הוסרה מועמדות",
  closed: "סגור",
};

const recruitmentStatusTones: Record<RecruitmentStatus, Tone> = {
  saved: "neutral",
  applied: "progress",
  recruiter_screen: "progress",
  interview: "progress",
  assignment: "progress",
  final_stage: "warning",
  offer: "success",
  accepted: "success",
  rejected: "blocker",
  withdrawn: "neutral",
  closed: "neutral",
};

const recruitmentStatusIcons: Record<RecruitmentStatus, LucideIcon> = {
  saved: Clock,
  applied: Send,
  recruiter_screen: PhoneCall,
  interview: UserRound,
  assignment: ClipboardList,
  final_stage: Trophy,
  offer: BadgeCheck,
  accepted: CircleCheck,
  rejected: CircleX,
  withdrawn: CircleSlash,
  closed: Archive,
};

export const recruitmentStatuses = Object.keys(recruitmentStatusLabels) as RecruitmentStatus[];

export const recruitmentStatusLabel = (status: string): string =>
  status in recruitmentStatusLabels ? recruitmentStatusLabels[status as RecruitmentStatus] : status;

export const recruitmentStatusTone = (status: string): Tone =>
  status in recruitmentStatusTones ? recruitmentStatusTones[status as RecruitmentStatus] : "neutral";

export const recruitmentStatusIcon = (status: string): LucideIcon =>
  status in recruitmentStatusIcons ? recruitmentStatusIcons[status as RecruitmentStatus] : Clock;
