import type { ApplicationDetail } from "@/api/contracts";
import { cx } from "@/ui/cx";
import { ExternalSubmissionAction } from "./ExternalSubmissionAction";
import { RecruitmentCorrectionAction } from "./RecruitmentCorrectionAction";
import { RecruitmentTimeline } from "./RecruitmentTimeline";

interface RecruitmentHistoryPanelProps {
  className?: string;
  detail: ApplicationDetail;
  onChanged: () => void;
}

export const RecruitmentHistoryPanel = ({ className, detail, onChanged }: RecruitmentHistoryPanelProps) => (
  <section
    aria-labelledby="recruitment-history-heading"
    className={cx("min-w-0 rounded-surface bg-cv-surface-muted p-4 sm:p-5", className)}
  >
    <div className="flex flex-wrap items-center justify-between gap-3">
      <div>
        <h3 className="font-semibold text-cv-text" id="recruitment-history-heading">
          היסטוריית המועמדות
        </h3>
        <p className="mt-1 text-support text-cv-text-muted">אירועי הסטטוס, המשימות וההגשות שנרשמו.</p>
      </div>
      <ExternalSubmissionAction detail={detail} onChanged={onChanged} />
    </div>
    <RecruitmentTimeline items={detail.recruitment_timeline} />

    <details className="mt-5 border-t border-cv-border pt-4 text-support">
      <summary className="cursor-pointer font-semibold text-cv-text">תיקון היסטוריה</summary>
      <div className="mt-3">
        <RecruitmentCorrectionAction detail={detail} onChanged={onChanged} />
      </div>
    </details>
  </section>
);
