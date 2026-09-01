import { useQueryClient } from "@tanstack/react-query";

import { applicationDetailQueryKey, applicationListQueryPrefix } from "../../api/applications";
import type { ApplicationDetail } from "../../api/contracts";
import { RecruitmentExceptionalActions } from "./RecruitmentExceptionalActions";
import { RecruitmentNextActionForm } from "./RecruitmentNextActionForm";
import { RecruitmentTimeline } from "./RecruitmentTimeline";
import { RecruitmentTransitionForm } from "./RecruitmentTransitionForm";

export const RecruitmentPanel = ({ detail }: { detail: ApplicationDetail }) => {
  const applicationId = detail.application.id;
  const queryClient = useQueryClient();

  const refresh = () => {
    void queryClient.invalidateQueries({ queryKey: applicationDetailQueryKey(applicationId) });
    void queryClient.invalidateQueries({ queryKey: applicationListQueryPrefix });
  };

  return (
    <section aria-labelledby="recruitment-heading">
      <div className="border-b border-cv-border pb-4">
        <h2 className="text-body font-semibold text-cv-text" id="recruitment-heading">
          מעקב גיוס
        </h2>
        <p className="mt-1 text-support leading-6 text-cv-text-muted">עדכון התקדמות התהליך ותכנון הצעד הבא.</p>
      </div>

      <div className="mt-5 grid gap-6 rounded-surface bg-cv-surface-muted p-4 sm:p-5 lg:grid-cols-2">
        <RecruitmentTransitionForm detail={detail} onChanged={refresh} />
        <RecruitmentNextActionForm detail={detail} onChanged={refresh} />
      </div>

      <div className="mt-6 border-t border-cv-border pt-5">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <h3 className="font-semibold text-cv-text">ציר הזמן</h3>
          <RecruitmentExceptionalActions detail={detail} onChanged={refresh} />
        </div>
        <RecruitmentTimeline items={detail.recruitment_timeline} />
      </div>
    </section>
  );
};
