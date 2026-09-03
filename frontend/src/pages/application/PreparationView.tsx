import { type ReactNode, useCallback, useState } from "react";

import type { Classification } from "../../api/analyses";
import type { ApplicationDetail } from "../../api/contracts";
import { Callout } from "../../ui/Callout";
import { surfaceClasses } from "../../ui/Surface";
import { ApplicationActions } from "./ApplicationActions";
import { AutomaticDraftNotice } from "./AutomaticDraftNotice";
import { PreparationAlerts } from "./PreparationAlerts";
import { ReviewDecisionPanel, resolvedByDecisionForm } from "./ReviewDecisionPanel";
import { AnalysisPanel } from "./analysis/AnalysisPanel";
import { GAP_REASON } from "./ReviewDecisionForm";

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

  /* Which hard gaps the reader has marked as knowingly accepted. It lives here because the
     mark is taken on the gap in the analysis panel and sent from the decision panel below
     it - two siblings, one decision, so the state belongs to the parent they share rather
     than being duplicated into each.

     Cleared on a successful commit, in the same beat the form clears: what was accepted is
     then part of the new SelectionPlan the refreshed projection reports, and leaving the
     marks would show a decision as pending after it landed. */
  const [acceptedRequirementIds, setAcceptedRequirementIds] = useState<string[]>([]);
  const toggleAcceptance = useCallback((requirementId: string) => {
    setAcceptedRequirementIds((current) =>
      current.includes(requirementId) ? current.filter((id) => id !== requirementId) : [...current, requirementId],
    );
  }, []);
  const clearAcceptances = useCallback(() => setAcceptedRequirementIds([]), []);

  /* Offered only while the projection is asking for that decision, and only against the
     plan the acceptance would be recorded on. Anything else - a gap the reader is merely
     reading, an analysis with no active plan - keeps the section read-only. */
  const gapDecisionOpen =
    detail.active_selection_plan_id != null && detail.review_reasons.some((reason) => reason.code === GAP_REASON);
  const acceptableGaps =
    classification === null
      ? []
      : classification.gaps.filter((gap) => gap.severity === "hard" && gap.requirementId !== null);

  return (
    <div className="flex flex-col gap-5">
      {/* Live work is reported before the alert backdrop, beside the workflow it is
          changing rather than on a separate screen. */}
      {operationPanel}

      <AutomaticDraftNotice detail={detail} />

      <PreparationAlerts detail={detail} />

      {classification === null ? null : (
        <AnalysisPanel
          classification={classification}
          detail={detail}
          gapAcceptance={
            gapDecisionOpen ? { disabled: false, onToggle: toggleAcceptance, selected: acceptedRequirementIds } : null
          }
        />
      )}

      {/* A superseded analysis is not shown as if it were the one in force: the reader is
          told the analysis on record belongs to an older snapshot and that a new one is
          what the workflow is waiting on. The projection's stale and review reasons carry
          the action. */}
      {supersededAnalysis ? (
        <Callout title="הניתוח שעל המסך אינו הניתוח הפעיל" tone="warning">
          הניתוח האחרון שנשמר נעשה מול תצלום משרה קודם, ולכן אינו מוצג כאן. ניתוח חדש מול התצלום הפעיל הוא מה שיציג את
          הסיווג העדכני.
        </Callout>
      ) : null}

      {/* The decision stays directly under the analysis it answers. Together with the
          projected next action it gets a distinct surface, so the way forward does not
          read as one more alert in the backdrop above. */}
      {hasActionSurface ? (
        <section
          aria-label={hasRecommendation ? "הפעולה המומלצת" : "פעולות זמינות"}
          className={
            hasRecommendation
              ? "rounded-surface border-2 border-cv-accent/25 bg-cv-accent-soft/40 p-5 shadow-surface"
              : surfaceClasses("bg-cv-surface p-5")
          }
        >
          <div className="flex flex-col gap-5">
            <ReviewDecisionPanel
              acceptableGapCount={acceptableGaps.length}
              acceptedRequirementIds={acceptedRequirementIds}
              detail={detail}
              onAcceptancesApplied={clearAcceptances}
            />
            <ApplicationActions detail={detail} onQueued={onQueued} />
          </div>
        </section>
      ) : null}
    </div>
  );
};
