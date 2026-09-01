import type { ReactNode } from "react";

import type { Classification } from "../../api/analyses";
import type { ApplicationDetail } from "../../api/contracts";
import { ApplicationActions } from "./ApplicationActions";
import { AutomaticDraftNotice } from "./AutomaticDraftNotice";
import { PreparationAlerts } from "./PreparationAlerts";
import { ReviewDecisionPanel, resolvedByDecisionForm } from "./ReviewDecisionPanel";
import { AnalysisPanel } from "./analysis/AnalysisPanel";
import { SupersededAnalysisNote } from "./analysis/SupersededAnalysisNote";

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
  /* Two different claims, kept apart. A recommendation is the projection naming the one
     action the workflow is waiting on - `recommended_action`, or a review decision this
     screen holds the control for. Offered actions are merely what is permitted.

     The surface appeared for either and announced itself as "the recommended action" for
     both, so an Application with three permitted actions and no recommendation got an
     emphasized panel promising guidance the projection had not given. The panel still
     appears - the actions have to live somewhere - it just says which of the two it is. */
  const hasRecommendation = detail.review_reasons.some(resolvedByDecisionForm) || detail.recommended_action != null;
  const hasActionSurface = hasRecommendation || detail.available_actions.length > 0;

  return (
    <div className="flex flex-col gap-5">
      {/* Live work is reported before the alert backdrop, beside the workflow it is
          changing rather than on a separate screen. */}
      {operationPanel}

      <AutomaticDraftNotice detail={detail} />

      <PreparationAlerts detail={detail} />

      {classification === null ? null : <AnalysisPanel classification={classification} detail={detail} />}

      {supersededAnalysis ? <SupersededAnalysisNote /> : null}

      {/* The decision stays directly under the analysis it answers. Together with the
          projected next action it gets a distinct surface, so the way forward does not
          read as one more alert in the backdrop above. */}
      {hasActionSurface ? (
        <section
          aria-label={hasRecommendation ? "הפעולה המומלצת" : "פעולות זמינות"}
          className={
            hasRecommendation
              ? "rounded-surface border-2 border-cv-accent/25 bg-cv-accent-soft/40 p-5 shadow-surface"
              : "rounded-surface border border-cv-border bg-cv-surface p-5"
          }
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
