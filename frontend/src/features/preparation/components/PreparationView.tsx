import { useQuery } from "@tanstack/react-query";
import { useState } from "react";

import { classificationFromAnalysis, selectionPlanQueryOptions } from "@/api/analyses";
import type { ApplicationDetail } from "@/api/contracts";
import { surfaceClasses } from "@/ui/surface";
import { TabPanel, Tabs, type TabSpec } from "@/ui/Tabs";
import { openDecisionCount, openDecisions, resolvedByReviewDecision } from "../model/reviewDecisions";
import { hasWorkflowActionsContent, workflowActionPlan } from "../model/workflowActionPlan";
import { AnalysisStatusBanner } from "./AnalysisStatusBanner";
import { AutomaticDraftNotice } from "./AutomaticDraftNotice";
import { PreparationAlerts } from "./PreparationAlerts";
import { ReanalyzeCard } from "./ReanalyzeCard";
import { ReviewDecisionPanel } from "./ReviewDecisionPanel";
import { SelectionPlanPanel } from "./SelectionPlanPanel";
import { WorkflowActions } from "./WorkflowActions";
import { AnalysisPanel } from "./analysis/AnalysisPanel";
import { GapsSection } from "./analysis/GapsSection";

type PreparationTab = "decisions" | "facts" | "analysis";

const TAB_GROUP = "preparation";

/* The CV preparation workflow for one Application: what has to be decided, which facts
   the CV will carry, and what the analysis found.

   It reads the projection once - the action plan, the classification, the open decisions -
   and hands the result down, so every control on the screen is drawn from the same
   answer rather than from four independent re-derivations of it. */
export const PreparationView = ({
  detail,
  onQueued,
}: {
  detail: ApplicationDetail;
  onQueued: (operationId: string) => void;
}) => {
  /* The active analysis as this screen reads it, and the case where the newest stored
     analysis is not it: an analysis of a superseded job snapshot is on record but is not
     what the workflow is standing on, so it is reported as absent and said to be. */
  const classification = classificationFromAnalysis(detail);
  const supersededAnalysis = classification === null && detail.latest_analysis != null;

  /* Two different claims, kept apart. A recommendation is the projection naming the one
     action the workflow is waiting on - `recommended_action`, or a review decision this
     screen holds the control for. Offered actions are merely what is permitted.

     The surface appeared for either and announced itself as "the recommended action" for
     both, so an Application with three permitted actions and no recommendation got an
     emphasized panel promising guidance the projection had not given. The panel still
     appears - the actions have to live somewhere - it just says which of the two it is. */
  const open = openDecisions(detail);
  const decisionCount = openDecisionCount(open);
  const hasRecommendation = detail.review_reasons.some(resolvedByReviewDecision) || detail.recommended_action != null;
  const plan = workflowActionPlan(detail);
  const hasActionSurface = hasWorkflowActionsContent(plan);

  /* Which hard gaps the reader has marked as knowingly accepted. It lives here because the
     mark is taken on the gap beside the decision panel and sent from that panel - two
     siblings, one decision, so the state belongs to the parent they share rather than
     being duplicated into each.

     Cleared on a successful commit, in the same beat the form clears: what was accepted is
     then part of the new SelectionPlan the refreshed projection reports, and leaving the
     marks would show a decision as pending after it landed. */
  const [acceptedRequirementIds, setAcceptedRequirementIds] = useState<string[]>([]);
  const toggleAcceptance = (requirementId: string) =>
    setAcceptedRequirementIds((current) =>
      current.includes(requirementId) ? current.filter((id) => id !== requirementId) : [...current, requirementId],
    );

  const acceptableGaps =
    classification === null
      ? []
      : classification.gaps.filter((gap) => gap.severity === "hard" && gap.requirementId !== null);

  /* The same plan the fact tab reads, asked for by the same key: React Query answers both
     from one request. It is read here only to count what the tab's badge announces - the
     panel below still owns every command against it. */
  const selectionPlanAction = plan.createSelectionPlan;
  const activePlanId = selectionPlanAction?.selectionPlanId ?? null;
  const planQuery = useQuery({
    ...selectionPlanQueryOptions(activePlanId ?? ""),
    enabled: selectionPlanAction !== null && activePlanId !== null,
  });

  const tabs: TabSpec<PreparationTab>[] = [
    { badge: decisionCount, badgeTone: "warning", id: "decisions", label: "החלטות נדרשות" },
    ...(selectionPlanAction === null
      ? []
      : [{ badge: planQuery.data?.candidates.length ?? null, id: "facts", label: "עובדות לקורות החיים" } as const]),
    ...(classification === null ? [] : [{ id: "analysis", label: "פרטי ניתוח ואבחון" } as const]),
  ];

  const [requestedTab, setRequestedTab] = useState<PreparationTab>("decisions");
  /* The tabs follow the projection, so one can disappear under the reader - an analysis
     that becomes superseded takes the diagnostics tab with it. The active tab is therefore
     derived rather than stored: a tab that is gone falls back to the first that remains
     instead of leaving the screen with no visible panel. */
  const activeTab = tabs.some((tab) => tab.id === requestedTab) ? requestedTab : (tabs[0]?.id ?? "decisions");

  return (
    <div className="flex flex-col gap-5">
      <AutomaticDraftNotice detail={detail} />

      {/* The verdict the whole screen is about, stated once and first. */}
      <AnalysisStatusBanner
        classification={classification}
        decisionCount={decisionCount}
        onShowDiagnostics={tabs.some((tab) => tab.id === "analysis") ? () => setRequestedTab("analysis") : null}
        supersededAnalysis={supersededAnalysis}
      />

      <Tabs
        active={activeTab}
        group={TAB_GROUP}
        label="חלקי מסך ההכנה"
        onSelect={setRequestedTab}
        tabs={tabs}
        variant="segmented"
      />

      <TabPanel active={activeTab === "decisions"} group={TAB_GROUP} tab="decisions">
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
          onAcceptancesApplied={() => setAcceptedRequirementIds([])}
        />

        {hasActionSurface ? (
          <section
            aria-label={hasRecommendation ? "הפעולה המומלצת" : "פעולות זמינות"}
            className={
              hasRecommendation
                ? "rounded-surface border-2 border-cv-accent/25 bg-cv-accent-soft/40 p-5 shadow-surface"
                : surfaceClasses("bg-cv-surface p-5")
            }
          >
            <WorkflowActions detail={detail} onQueued={onQueued} plan={plan} />
          </section>
        ) : null}
      </TabPanel>

      {selectionPlanAction === null ? null : (
        <TabPanel active={activeTab === "facts"} group={TAB_GROUP} tab="facts">
          <SelectionPlanPanel action={selectionPlanAction} detail={detail} onQueued={onQueued} />
        </TabPanel>
      )}

      {classification === null ? null : (
        <TabPanel active={activeTab === "analysis"} group={TAB_GROUP} tab="analysis">
          <AnalysisPanel classification={classification} detail={detail} showGaps={!open.gaps} />
          <ReanalyzeCard detail={detail} onQueued={onQueued} plan={plan} />
        </TabPanel>
      )}
    </div>
  );
};
