import type { ReactNode } from "react";

import type { Classification } from "../../api/analyses";
import type { ApplicationDetail } from "../../api/contracts";
import { AnalysisPanel, SupersededAnalysisNote } from "./AnalysisPanel";
import { ArtifactsPanel } from "./ArtifactsPanel";
import { ApplicationActions } from "./ApplicationActions";
import { JobPostingUpdate } from "./JobPostingUpdate";
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
    <div className="flex flex-col gap-5">
      {/* Live work is reported before the alert backdrop, beside the workflow it is
          changing rather than on a separate screen. */}
      {operationPanel}

      <PreparationAlerts automaticAnalysisStartFailed={automaticAnalysisStartFailed} detail={detail} />

      {/* The posting the analysis was run against precedes the analysis itself: input
          before conclusion. Both stay under the same condition because the snapshot on
          its own is not what this screen is for. */}
      {classification === null ? null : <JobSnapshotPanel detail={detail} />}

      {classification === null ? null : <AnalysisPanel classification={classification} detail={detail} />}

      {/* Beside the posting rather than behind a stage: a posting can be amended at any
          point in the Application's life, including before it was ever analyzed and after
          a revision was approved from it. It stays a closed section, because the reader
          who came to this screen came for the analysis and its decision, not to retype a
          posting that has not changed. */}
      <JobPostingUpdate detail={detail} />

      {supersededAnalysis ? <SupersededAnalysisNote /> : null}

      {/* Product spec §14: the Application's own revisions-and-artifacts section. It
          follows the posting and the analysis because it is their output, and it renders
          itself away until something has actually been registered. */}
      <ArtifactsPanel applicationId={detail.application.id} />

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
