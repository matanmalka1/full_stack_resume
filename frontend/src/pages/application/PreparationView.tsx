import { useQuery } from "@tanstack/react-query";
import { type ReactNode, useCallback, useMemo, useState } from "react";

import { type Classification, selectionPlanQueryOptions } from "../../api/analyses";
import type { ApplicationDetail } from "../../api/contracts";
import { surfaceClasses } from "../../ui/Surface";
import { ApplicationActions } from "./ApplicationActions";
import { AutomaticDraftNotice } from "./AutomaticDraftNotice";
import { PreparationAlerts } from "./PreparationAlerts";
import { ReviewDecisionPanel } from "./ReviewDecisionPanel";
import { SelectionPlanPanel } from "./SelectionPlanPanel";
import { AnalysisPanel } from "./analysis/AnalysisPanel";
import { GapsSection } from "./analysis/GapsSection";
import { openDecisionCount, openDecisions, resolvedByDecisionForm } from "./ReviewDecisionForm";
import { applicationActionPlan } from "./applicationActionPlan";
import { AnalysisStatusBanner } from "./preparation/AnalysisStatusBanner";
import {
  type PreparationTab,
  type PreparationTabSpec,
  PreparationTabPanel,
  PreparationTabs,
} from "./preparation/PreparationTabs";

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
  const open = openDecisions(detail);
  const decisionCount = openDecisionCount(open);
  const hasRecommendation = detail.review_reasons.some(resolvedByDecisionForm) || detail.recommended_action != null;
  const hasActionSurface = hasRecommendation || detail.available_actions.length > 0;

  /* Which hard gaps the reader has marked as knowingly accepted. It lives here because the
     mark is taken on the gap beside the decision panel and sent from that panel - two
     siblings, one decision, so the state belongs to the parent they share rather than
     being duplicated into each.

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

  const acceptableGaps =
    classification === null
      ? []
      : classification.gaps.filter((gap) => gap.severity === "hard" && gap.requirementId !== null);

  /* The same plan the fact tab reads, asked for by the same key: React Query answers both
     from one request. It is read here only to count what the tab's badge announces - the
     panel below still owns every command against it. */
  const selectionPlanAction = applicationActionPlan(detail).createSelectionPlan;
  const activePlanId = selectionPlanAction?.selectionPlanId ?? null;
  const planQuery = useQuery({
    ...selectionPlanQueryOptions(activePlanId ?? ""),
    enabled: selectionPlanAction !== null && activePlanId !== null,
  });

  const tabs = useMemo((): PreparationTabSpec[] => {
    const factCount = planQuery.data?.candidates.length ?? null;

    return [
      { badge: decisionCount, id: "decisions", label: "החלטות נדרשות" },
      ...(selectionPlanAction === null
        ? []
        : [{ badge: factCount, id: "facts", label: "עובדות לקורות החיים" } satisfies PreparationTabSpec]),
      ...(classification === null
        ? []
        : [{ badge: null, id: "analysis", label: "פרטי ניתוח ואבחון", secondary: true } satisfies PreparationTabSpec]),
    ];
  }, [classification, decisionCount, planQuery.data, selectionPlanAction]);

  const [requestedTab, setRequestedTab] = useState<PreparationTab>("decisions");
  /* The tabs follow the projection, so one can disappear under the reader - an analysis
     that becomes superseded takes the diagnostics tab with it. The active tab is therefore
     derived rather than stored: a tab that is gone falls back to the first that remains
     instead of leaving the screen with no visible panel. */
  const activeTab = tabs.some((tab) => tab.id === requestedTab) ? requestedTab : (tabs[0]?.id ?? "decisions");

  const actionSurface = hasActionSurface ? (
    <section
      aria-label={hasRecommendation ? "הפעולה המומלצת" : "פעולות זמינות"}
      className={
        hasRecommendation
          ? "rounded-surface border-2 border-cv-accent/25 bg-cv-accent-soft/40 p-5 shadow-surface"
          : surfaceClasses("bg-cv-surface p-5")
      }
    >
      <ApplicationActions detail={detail} onQueued={onQueued} />
    </section>
  ) : null;

  return (
    <div className="flex flex-col gap-5">
      {/* Live work is reported before everything else, beside the workflow it is changing
          rather than on a separate screen. */}
      {operationPanel}

      <AutomaticDraftNotice detail={detail} />

      {/* The verdict the whole screen is about, stated once and first. */}
      <AnalysisStatusBanner
        classification={classification}
        decisionCount={decisionCount}
        onShowDiagnostics={tabs.some((tab) => tab.id === "analysis") ? () => setRequestedTab("analysis") : null}
        supersededAnalysis={supersededAnalysis}
      />

      <PreparationTabs active={activeTab} onSelect={setRequestedTab} tabs={tabs} />

      <PreparationTabPanel active={activeTab === "decisions"} tab="decisions">
        <PreparationAlerts detail={detail} />

        {/* A hard-gap decision is taken on the exact gap it is about, so while the
            projection is asking for one the gaps stand with the decision panel rather than
            in the diagnostics tab. */}
        {open.gaps && classification !== null ? (
          <section aria-label="פערים להכרעה" className={surfaceClasses("bg-cv-surface p-5")}>
            <GapsSection
              acceptance={{ disabled: false, onToggle: toggleAcceptance, selected: acceptedRequirementIds }}
              gaps={classification.gaps}
            />
          </section>
        ) : null}

        <ReviewDecisionPanel
          acceptableGapCount={acceptableGaps.length}
          acceptedRequirementIds={acceptedRequirementIds}
          classification={classification}
          detail={detail}
          onAcceptancesApplied={clearAcceptances}
        />

        {actionSurface}
      </PreparationTabPanel>

      {selectionPlanAction === null ? null : (
        <PreparationTabPanel active={activeTab === "facts"} tab="facts">
          <SelectionPlanPanel detail={detail} onQueued={onQueued} />
        </PreparationTabPanel>
      )}

      {classification === null ? null : (
        <PreparationTabPanel active={activeTab === "analysis"} tab="analysis">
          <AnalysisPanel classification={classification} detail={detail} showGaps={!open.gaps} />
        </PreparationTabPanel>
      )}
    </div>
  );
};
