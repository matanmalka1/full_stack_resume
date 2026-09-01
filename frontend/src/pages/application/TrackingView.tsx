import type { ApplicationDetail } from "../../api/contracts";
import { RecruitmentPanel } from "../recruitment/RecruitmentPanel";

export const TrackingView = ({ detail }: { detail: ApplicationDetail }) => <RecruitmentPanel detail={detail} />;
