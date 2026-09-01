import type { ApplicationDetail } from "../../api/contracts";
import { RecruitmentPanel } from "../recruitment/RecruitmentPanel";

export const TrackingView = ({ detail }: { detail: ApplicationDetail }) => (
  <div aria-labelledby="application-view-tab-tracking" id="application-view-tracking" role="tabpanel">
    <RecruitmentPanel detail={detail} />
  </div>
);
