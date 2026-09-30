import type { ClassValue } from "@/ui/cx";
import { StatusBadge } from "@/ui/StatusBadge";
import { recruitmentStatusIcon, recruitmentStatusLabel, recruitmentStatusTone } from "../model/recruitmentStatus";

/* One reading of a recruitment status as a badge: the same Hebrew label, tone and icon on
   the manager's summary and on a search result. The board's quieter dot-and-word pill is a
   separate, deliberate treatment and stays with the board. */
export const RecruitmentStatusBadge = ({ className, status }: { className?: ClassValue; status: string }) => (
  <StatusBadge className={className} icon={recruitmentStatusIcon(status)} tone={recruitmentStatusTone(status)}>
    {recruitmentStatusLabel(status)}
  </StatusBadge>
);
