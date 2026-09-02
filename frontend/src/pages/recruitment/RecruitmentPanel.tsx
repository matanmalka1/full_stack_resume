import { useQueryClient } from "@tanstack/react-query";
import { useState } from "react";

import { invalidateApplicationViews } from "../../api/applications";
import type { ApplicationDetail } from "../../api/contracts";
import { Button, buttonClasses } from "../../ui/Button";
import { Card } from "../../ui/Card";
import { SectionHeader } from "../../ui/SectionHeader";
import { StatusBadge } from "../../ui/StatusBadge";
import { formatDate } from "../../ui/formatDateTime";
import { recruitmentStatusLabel } from "../application/applicationLabels";
import { RecruitmentExceptionalActions } from "./RecruitmentExceptionalActions";
import { RecruitmentTimeline } from "./RecruitmentTimeline";
import { RecruitmentUpdateDialog } from "./RecruitmentUpdateDialog";

export const RecruitmentPanel = ({ detail }: { detail: ApplicationDetail }) => {
  const applicationId = detail.application.id;
  const queryClient = useQueryClient();
  const [updateOpen, setUpdateOpen] = useState(false);

  const refresh = () => {
    void invalidateApplicationViews(queryClient, applicationId);
  };

  return (
    <Card aria-labelledby="recruitment-heading" className="bg-cv-surface p-4 shadow-surface sm:p-5">
      <SectionHeader
        description="עדכון התקדמות התהליך ותכנון הצעד הבא."
        headingId="recruitment-heading"
        headingSize="body"
        leadingDescription
        spacing="roomy"
        title="מעקב גיוס"
      />

      <div className="mt-5 rounded-surface bg-cv-surface-muted p-4 sm:p-5">
        <div className="grid gap-4 sm:grid-cols-2">
          <div>
            <p className="text-support font-semibold text-cv-text-muted">השלב בתהליך</p>
            <StatusBadge className="mt-2 px-3 py-1" tone="neutral">
              {recruitmentStatusLabel(detail.recruitment_status)}
            </StatusBadge>
          </div>
          <div>
            <p className="text-support font-semibold text-cv-text-muted">הצעד הבא</p>
            <p className="mt-2 text-body font-semibold text-cv-text" dir="auto">
              {detail.application.next_action ?? "לא נקבע צעד הבא"}
            </p>
            {detail.application.next_action_date == null ? null : (
              <p className="mt-1 text-support text-cv-text-muted">
                תאריך יעד: {formatDate(detail.application.next_action_date)}
              </p>
            )}
          </div>
        </div>

        <div className="mt-5 flex flex-wrap items-start justify-between gap-3 border-t border-cv-border pt-4">
          <Button onClick={() => setUpdateOpen(true)}>עדכון סטטוס ומשימה</Button>
          <details className="relative text-support">
            <summary className={buttonClasses("secondary", "cursor-pointer list-none")}>פעולות נוספות</summary>
            <div className="absolute end-0 z-10 mt-2 flex w-56 flex-col gap-2 rounded-control border border-cv-border bg-cv-surface p-2 shadow-floating">
              <RecruitmentExceptionalActions detail={detail} kind="external-submission" onChanged={refresh} />
              <RecruitmentExceptionalActions detail={detail} kind="correction" onChanged={refresh} />
            </div>
          </details>
        </div>
      </div>

      <RecruitmentUpdateDialog
        application={updateOpen ? detail.application : null}
        onClose={() => setUpdateOpen(false)}
      />

      <div className="mt-6 border-t border-cv-border pt-5">
        <h3 className="font-semibold text-cv-text">ציר הזמן</h3>
        <RecruitmentTimeline items={detail.recruitment_timeline} />
      </div>
    </Card>
  );
};
