import { CalendarClock } from "lucide-react";

import type { ApplicationDetail } from "@/api/contracts";
import { StatusBadge } from "@/ui/StatusBadge";
import { formatDate } from "@/ui/formatDateTime";
import { recruitmentStatusIcon, recruitmentStatusLabel, recruitmentStatusTone } from "@/features/applications/model/applicationLabels";

export const RecruitmentSummary = ({ detail }: { detail: ApplicationDetail }) => (
  <section
    aria-label="מצב המועמדות"
    className="relative overflow-hidden rounded-surface border border-cv-border bg-cv-surface-muted p-4 shadow-inner"
  >
    <span aria-hidden="true" className="absolute inset-y-0 start-0 w-1 bg-cv-accent" />
    <div className="grid gap-4 ps-2 sm:grid-cols-[auto_minmax(0,1fr)] sm:items-center">
      <div>
        <p className="text-support font-semibold text-cv-text-muted">השלב הנוכחי</p>
        <StatusBadge
          className="mt-2"
          icon={recruitmentStatusIcon(detail.recruitment_status)}
          tone={recruitmentStatusTone(detail.recruitment_status)}
        >
          {recruitmentStatusLabel(detail.recruitment_status)}
        </StatusBadge>
      </div>
      <div className="min-w-0 sm:border-s sm:border-cv-border sm:ps-4">
        <p className="text-support font-semibold text-cv-text-muted">הפעולה הבאה</p>
        <p className="mt-1 font-semibold text-cv-text" dir="auto">
          {detail.application.next_action ?? "לא נקבעה פעולה נוספת"}
        </p>
        {detail.application.next_action_date == null ? null : (
          <p className="mt-1 inline-flex items-center gap-1.5 text-support text-cv-text-muted">
            <CalendarClock aria-hidden="true" className="size-4" />
            יעד: {formatDate(detail.application.next_action_date)}
          </p>
        )}
      </div>
    </div>
  </section>
);
