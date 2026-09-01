import type { ReactNode } from "react";

import type { Classification } from "../../api/analyses";
import type { ApplicationDetail } from "../../api/contracts";
import { AnalysisPanel, SupersededAnalysisNote } from "./AnalysisPanel";
import { ApplicationActions } from "./ApplicationActions";
import { PreparationAlerts } from "./PreparationAlerts";
import { ReviewDecisionPanel, resolvedByDecisionForm } from "./ReviewDecisionPanel";

export const PreparationView = ({
  classification,
  detail,
  onQueued,
  operationPanel,
  supersededAnalysis,
}: {
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

      <PreparationAlerts detail={detail} />

      {classification === null ? null : <AnalysisPanel classification={classification} detail={detail} />}

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
