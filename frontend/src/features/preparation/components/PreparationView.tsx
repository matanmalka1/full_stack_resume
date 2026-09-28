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

/* Preparing one Application's CV, as a single step of the workflow wizard.

   The step reads in one direction: the verdict (the banner), then two columns.

   - The side column holds what the reader *does*: the workflow's next action and the
     matching configuration the analysis and selection are built from. It is short by
     construction, so it can stay pinned beside the long column while that scrolls - the
     fact list used to live here too, which made the "sticky" column the taller one and
     the pin never took hold.
   - The main column holds what the reader *checks*, in the order they check it: what the
     analysis read from the posting and how the approved facts cover it, then which facts
     the CV will carry and why. The selection follows the analysis because it answers it:
     each fact names the requirements it covers, and each requirement says whether its
     facts made it into the CV.

   Nothing is stated twice across the columns. The fit verdict is the banner's, the
   classification values are the configuration form's, and the analysis panel no longer
   restates either. */
export const PreparationView = ({
  detail,
  onQueued,
  operationLive,
}: {
  detail: ApplicationDetail;
  onQueued: (operationId: string) => void;
  /* Whether this Application's work is under way, by `isOperationLive`: the actions that
     change what a run replaces wait for it, whether or not its overlay is showing. */
  operationLive: boolean;
}) => {
  const [matchingSaved, setMatchingSaved] = useState<AnalysisDecisions | null>(null);
  const matchingSaveInContext =
    matchingSaved?.application_id === detail.application.id &&
    matchingSaved.job_analysis_id === detail.active_analysis_id &&
    matchingSaved.selection_plan_id === detail.active_selection_plan_id;
  const classification = classificationFromAnalysis(detail);
  /* The active analysis as this screen reads it: an analysis of a superseded job snapshot
     is on record but is not what the workflow stands on, so it is reported as absent. */
  const supersededAnalysis = classification === null && detail.latest_analysis != null;

  const plan = workflowActionPlan(detail);
  const hasRecommendation = detail.recommended_action != null;
  const selectionPlanAction = plan.createSelectionPlan;
  const hasMainColumn = classification !== null || selectionPlanAction !== null;

  return (
    <div className="flex flex-col gap-4">
      <AutomaticDraftNotice detail={detail} />

      {/* The verdict the step is about, stated once and first - whether or not anything
          is wrong, so a settled analysis still names its subject. */}
      <AnalysisStatusBanner classification={classification} supersededAnalysis={supersededAnalysis} />

      {/* Portalled past the shell's rail column by `WideRow`, so the two columns get the
          full measure rather than being inset by the rail's width for the whole step. */}
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

            {/* The CAS source pair is the local form's lifetime: a changed pair remounts
                the editor before older local choices can be submitted against it. */}
            {classification === null ? null : (
              <MatchingConfigurationEditor
                classification={classification}
                detail={detail}
                key={`${detail.active_analysis_id ?? "none"}:${detail.active_selection_plan_id ?? "none"}`}
                onSaved={setMatchingSaved}
              />
            )}

            {matchingSaveInContext && matchingSaved !== null && (
              // Callout renders a semantic output for its status prop.
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
