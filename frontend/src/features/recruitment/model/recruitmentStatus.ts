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
import type { StatusTone } from "@/ui/status";

export const recruitmentStatusLabels: Record<RecruitmentStatus, string> = {
  saved: "נשמר",
  applied: "הוגש",
  recruiter_screen: "שיחת מגייס",
  interview: "ראיון",
  assignment: "משימה",
  final_stage: "שלב סופי",
  offer: "הצעה",
  accepted: "התקבל",
  rejected: "נדחה",
  withdrawn: "בוטל",
  closed: "סגור",
};

const recruitmentStatusTones: Record<RecruitmentStatus, StatusTone> = {
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

export const recruitmentStatusTone = (status: string): StatusTone =>
  status in recruitmentStatusTones ? recruitmentStatusTones[status as RecruitmentStatus] : "neutral";

export const recruitmentStatusIcon = (status: string): LucideIcon =>
  status in recruitmentStatusIcons ? recruitmentStatusIcons[status as RecruitmentStatus] : Clock;
