import { CalendarClock } from "lucide-react";

import type { ApplicationDetail } from "@/api/contracts";
import { StatusBadge } from "@/ui/StatusBadge";
import { formatDate } from "@/utils/formatDateTime";
import { recruitmentStatusIcon, recruitmentStatusLabel, recruitmentStatusTone } from "../model/recruitmentStatus";

export const RecruitmentSummary = ({ detail }: { detail: ApplicationDetail }) => (
  <section
    /* The recruitment axis, named as one. It read "מצב המועמדות" - the state of the
       application - which was accurate while this block only ever appeared alone in the
       manager dialog. On the Application screen it sits beside the CV preparation state,
       and a region claiming the whole application's state next to one that holds half of
       it is the merge the two axes exist to avoid. */
    aria-label="מצב הגיוס"
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
        {detail.terminal_outcome == null ? null : (
          <p className="mt-2 text-support text-cv-text-muted">
            תוצאה סופית:{" "}
            <strong className="font-semibold text-cv-text">{recruitmentStatusLabel(detail.terminal_outcome)}</strong>
          </p>
        )}
      </div>
      <div className="min-w-0 sm:border-s sm:border-cv-border sm:ps-4">
        <p className="text-support font-semibold text-cv-text-muted">הפעולה הבאה</p>
        <p className="mt-1 font-semibold text-cv-text" dir="auto">
          {detail.application.next_action ?? "לא נקבעה פעולה נוספת"}
        </p>
        {detail.application.next_action_date == null ? null : (
          <p className="mt-1 inline-flex items-center gap-1.5 text-support text-cv-text-muted">
            <CalendarClock aria-hidden="true" className="size-icon-md" />
            יעד: {formatDate(detail.application.next_action_date)}
          </p>
        )}
      </div>
    </div>
  </section>
);
