import type { ReactNode } from "react";

import type { Classification } from "../../api/analyses";
import type { ApplicationDetail } from "../../api/contracts";
import { AnalysisPanel, SupersededAnalysisNote } from "./AnalysisPanel";
import { ApplicationActions } from "./ApplicationActions";
import { JobSnapshotPanel } from "./JobSnapshotPanel";
import { PreparationAlerts } from "./PreparationAlerts";
import { ReviewDecisionPanel, resolvedByDecisionForm } from "./ReviewDecisionPanel";

export const PreparationView = ({
  automaticAnalysisStartFailed,
  classification,
  detail,
  onQueued,
  operationPanel,
  supersededAnalysis,
}: {
  automaticAnalysisStartFailed: boolean;
  classification: Classification | null;
  detail: ApplicationDetail;
  onQueued: (operationId: string) => void;
  operationPanel: ReactNode;
  supersededAnalysis: boolean;
}) => {
  const hasRecommendedAction =
    detail.review_reasons.some(resolvedByDecisionForm) ||
    detail.recommended_action != null ||
    detail.available_actions.length > 0;

  return (
    <div
      aria-labelledby="application-view-tab-preparation"
      className="flex flex-col gap-5"
      id="application-view-preparation"
      role="tabpanel"
    >
      {/* Live work is reported before the alert backdrop, beside the workflow it is
          changing rather than on a separate screen. */}
      {operationPanel}

      <PreparationAlerts
        automaticAnalysisStartFailed={automaticAnalysisStartFailed}
        detail={detail}
      />

      {/* The posting the analysis was run against precedes the analysis itself: input
          before conclusion. Both stay under the same condition because the snapshot on
          its own is not what this screen is for. */}
      {classification === null ? null : <JobSnapshotPanel detail={detail} />}

      {classification === null ? null : (
        <AnalysisPanel classification={classification} detail={detail} />
      )}

      {supersededAnalysis ? <SupersededAnalysisNote /> : null}

      {/* The decision stays directly under the analysis it answers. Together with the
          projected next action it gets a distinct surface, so the way forward does not
          read as one more alert in the backdrop above. */}
      {hasRecommendedAction ? (
        <section
          aria-label="הפעולה המומלצת"
          className="rounded-surface border-2 border-cv-accent/25 bg-cv-accent-soft/40 p-5 shadow-surface"
        >
          <div className="flex flex-col gap-5">
            <ReviewDecisionPanel detail={detail} />
            <ApplicationActions detail={detail} onQueued={onQueued} />
          </div>
        </section>
      ) : null}
    </div>
  );
};
