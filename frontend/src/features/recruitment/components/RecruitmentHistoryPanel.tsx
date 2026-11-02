import { useState } from "react";

import type { ApplicationDetail } from "@/api/contracts";
import { DisclosureSummary } from "@/ui/Disclosure";
import { ExternalSubmissionAction } from "./ExternalSubmissionAction";
import { RecruitmentCorrectionAction } from "./RecruitmentCorrectionAction";
import { RecruitmentTimeline } from "./RecruitmentTimeline";

interface RecruitmentHistoryPanelProps {
  detail: ApplicationDetail;
  onChanged: () => void;
}

/* The body of the history dialog, whose title names it: the events on record, the way to
   add a submission made outside the system, and - folded, since it is the exception - the
   correction of an event recorded wrongly. */
export const RecruitmentHistoryPanel = ({ detail, onChanged }: RecruitmentHistoryPanelProps) => {
  const [correctionOpen, setCorrectionOpen] = useState(false);

  return (
    <div className="flex min-w-0 flex-col gap-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <p className="text-support text-cv-text-muted">אירועי הסטטוס, המשימות וההגשות שנרשמו.</p>
        <ExternalSubmissionAction detail={detail} onChanged={onChanged} />
      </div>
      <RecruitmentTimeline items={detail.recruitment_timeline} />

      <details
        className="border-t border-cv-hairline pt-4 text-support"
        onToggle={(event) => setCorrectionOpen(event.currentTarget.open)}
      >
        <DisclosureSummary className="font-semibold text-cv-text" open={correctionOpen}>
          תיקון היסטוריה
        </DisclosureSummary>
        <div className="mt-3">
          <RecruitmentCorrectionAction detail={detail} onChanged={onChanged} />
        </div>
      </details>
    </div>
  );
};
