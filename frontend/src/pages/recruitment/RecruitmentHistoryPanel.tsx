import type { ApplicationDetail } from "../../api/contracts";
import { ExternalSubmissionAction } from "./ExternalSubmissionAction";
import { RecruitmentCorrectionAction } from "./RecruitmentCorrectionAction";
import { RecruitmentTimeline } from "./RecruitmentTimeline";

interface RecruitmentHistoryPanelProps {
  detail: ApplicationDetail;
  onChanged: () => void;
}

export const RecruitmentHistoryPanel = ({ detail, onChanged }: RecruitmentHistoryPanelProps) => (
  <section
    aria-labelledby="recruitment-history-heading"
    className="min-w-0 lg:border-s lg:border-cv-border lg:ps-6"
  >
    <h3 className="font-semibold text-cv-text" id="recruitment-history-heading">
      היסטוריית המועמדות
    </h3>
    <RecruitmentTimeline items={detail.recruitment_timeline} />

    <details className="mt-5 border-t border-cv-border pt-4 text-support">
      <summary className="cursor-pointer font-semibold text-cv-text">פעולות נוספות</summary>
      <div className="mt-3 flex flex-wrap gap-2">
        <ExternalSubmissionAction detail={detail} onChanged={onChanged} />
        <RecruitmentCorrectionAction detail={detail} onChanged={onChanged} />
      </div>
    </details>
  </section>
);
