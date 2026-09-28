import { useState } from "react";

import { classificationFromAnalysis } from "@/api/analyses";
import { actionLabel } from "../model/preparationLabels";
import { Callout } from "@/ui/Callout";
import { WideRow } from "@/ui/WideRow";
import { cx } from "@/ui/cx";
import type { AnalysisDecisions, ApplicationDetail } from "@/api/contracts";
import { workflowActionPlan } from "../model/workflowActionPlan";
import { AnalysisStage } from "../stages/analysis/AnalysisStage";
import { SelectionPlanPanel } from "../stages/content/SelectionPlanPanel";
import { VerificationStage } from "../stages/verification/VerificationStage";
import { MatchingConfigurationEditor } from "../stages/matching/MatchingConfigurationEditor";
import { AnalysisStatusBanner } from "./AnalysisStatusBanner";
import { AutomaticDraftNotice } from "./AutomaticDraftNotice";

export const PreparationView = ({
  detail,
  onQueued,
  operationLive,
}: {
  detail: ApplicationDetail;
  onQueued: (operationId: string) => void;
  operationLive: boolean;
}) => {
  const [matchingSaved, setMatchingSaved] = useState<AnalysisDecisions | null>(null);
  const matchingSaveInContext =
    matchingSaved?.application_id === detail.application.id &&
    matchingSaved.job_analysis_id === detail.active_analysis_id &&
    matchingSaved.selection_plan_id === detail.active_selection_plan_id;
  const classification = classificationFromAnalysis(detail);
  const supersededAnalysis = classification === null && detail.latest_analysis != null;

  const plan = workflowActionPlan(detail);
  const hasRecommendation = detail.recommended_action != null;
  const selectionPlanAction = plan.createSelectionPlan;
  const hasMainColumn = classification !== null || selectionPlanAction !== null;

  return (
    <div className="flex flex-col gap-4">
      <AutomaticDraftNotice detail={detail} />

      <AnalysisStatusBanner classification={classification} supersededAnalysis={supersededAnalysis} />

      <WideRow>
        <div className="flex flex-col gap-6 lg:flex-row-reverse lg:items-start lg:gap-8 xl:gap-10">
          <div
            className={cx(
              "flex min-w-0 flex-col gap-6",
              hasMainColumn
                ? "lg:sticky lg:top-20 lg:max-h-[calc(100vh-6rem)] lg:-m-1 lg:basis-2/5 lg:overflow-y-auto lg:p-1 xl:basis-1/3"
                : "lg:flex-1",
            )}
          >
            <VerificationStage
              detail={detail}
              hasRecommendation={hasRecommendation}
              onQueued={onQueued}
              operationLive={operationLive}
              plan={plan}
            />

            {classification === null ? null : (
              // A new analysis/plan pair remounts the form so stale choices are never submitted.
              <MatchingConfigurationEditor
                classification={classification}
                detail={detail}
                key={`${detail.active_analysis_id ?? "none"}:${detail.active_selection_plan_id ?? "none"}`}
                onSaved={setMatchingSaved}
              />
            )}

            {matchingSaveInContext && matchingSaved !== null && (
              // oxlint-disable-next-line jsx-a11y/prefer-tag-over-role
              <Callout role="status" title="הגדרות ההתאמה נשמרו" tone="success">
                {matchingSaved.state.recommended_action == null
                  ? "מצב המועמדות עודכן לפי ההקשר החדש."
                  : `הצעד הבא לפי השרת: ${actionLabel(matchingSaved.state.recommended_action)}.`}
              </Callout>
            )}
          </div>

          {hasMainColumn ? (
            <div className="flex min-w-0 flex-1 flex-col gap-6">
              {classification === null ? null : (
                <AnalysisStage
                  classification={classification}
                  detail={detail}
                  onQueued={onQueued}
                  operationLive={operationLive}
                  plan={plan}
                />
              )}

              {selectionPlanAction === null ? null : (
                <SelectionPlanPanel
                  action={selectionPlanAction}
                  detail={detail}
                  onQueued={onQueued}
                  operationLive={operationLive}
                  requirements={classification?.requirements ?? []}
                />
              )}
            </div>
          ) : null}
        </div>
      </WideRow>
    </div>
  );
};
