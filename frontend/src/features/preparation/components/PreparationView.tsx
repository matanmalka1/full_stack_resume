import { useState } from "react";

import { classificationFromAnalysis } from "@/api/analyses";
import { actionLabel } from "../model/preparationLabels";
import { Callout } from "@/ui/Callout";
import { WideRow } from "@/ui/WideRow";
import type { AnalysisDecisions, ApplicationDetail } from "@/api/contracts";
import { workflowActionPlan } from "../model/workflowActionPlan";
import { AnalysisStage } from "../stages/analysis/AnalysisStage";
import { SelectionPlanPanel } from "../stages/content/SelectionPlanPanel";
import { VerificationStage } from "../stages/verification/VerificationStage";
import { MatchingConfigurationEditor } from "../stages/verification/MatchingConfigurationEditor";
import { AnalysisStatusBanner } from "./AnalysisStatusBanner";
import { AutomaticDraftNotice } from "./AutomaticDraftNotice";

/* Preparing one Application's CV, as a single step of the workflow wizard rather than a
   hub of tabs.

   The screen used to be a record you browsed: a tab bar over decisions, facts and the
   diagnosis, a second bar over the posting and the files, a two-axis state panel, and a
   recruitment column - several readings of the same projection side by side at the same
   weight. None of that is the task. The task is the one thing the workflow is waiting on,
   and it is stated once: the verdict, then the single action panel that answers it.

   What supported the old tabs is still reachable below the verdict, in the same reading
   order this list once put behind disclosures. The matching configuration and the full
   diagnosis render open, because a reader deciding whether to trust the verdict needs that
   picture without an extra click; only the facts-selection panel, a refinement of a later
   step rather than information about this one, still folds away until wanted.

   With the diagnosis open by default alongside the work, one narrow column stacked all of
   it - the facts checklist and the full requirement coverage both run long - into a single
   scroll a reader had to hold in their head at once. This is the other step whose body
   wants two readable columns rather than one: what changes this step (the action, the
   matching form, the facts checklist) beside what explains it (the verdict's reasoning),
   the same split `DraftWorkspace` draws between the editable draft and its evidence, at
   the same wide measure the shell gives that step for the same reason. The reasoning
   column reads wider than the work column here - 60/40 rather than an even split - because
   the diagnosis is prose and long lists, and the work column is mostly form controls. */
export const PreparationView = ({
  detail,
  onQueued,
}: {
  detail: ApplicationDetail;
  onQueued: (operationId: string) => void;
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

  return (
    <div className="flex flex-col gap-4">
      <AutomaticDraftNotice detail={detail} />

      {/* The verdict the step is about, stated once and first.

          It used to be drawn only when something was wrong or had been decided - a
          superseded analysis, a missing one, an open decision, an accepted risk. A clean
          analysis that nobody had to rule on therefore said nothing, and a finished
          Application opened on a step with no subject stated at all. The verdict of
          a settled analysis is still the verdict, and `bannerContent` has always had the
          sentence for it - fit and confidence, in the verdict's own tone. The banner now
          renders whenever this step renders, and which of its branches speaks stays that
          function's decision rather than being pre-empted here. */}
      <AnalysisStatusBanner classification={classification} supersededAnalysis={supersededAnalysis} />

      {/* The work column beside the reasoning column, at the same breakpoint
          `DraftWorkspace` uses. 40/60: see the file doc for why the split favours the
          reasoning column here rather than the work column.

          Wrapped in `WideRow`: `PageShell`'s landmark grid reserves the rail's 13rem
          column for this whole step's height, which would inset this row by that width
          even though the rail itself is only a few lines tall. `WideRow` portals it into
          the shell's `afterBody` slot instead, a later sibling of the grid rather than a
          box stretched to overlap it - see that component's doc for why a negative-margin
          bleed here isn't safe. The other rows - the draft notice, the verdict banner,
          the operation cards above this component - stay inset, reading beside the rail
          the way the rest of the step does; only this one moves. */}
      <WideRow>
        <div className="flex flex-col gap-6 lg:flex-row-reverse lg:items-start lg:gap-8 xl:gap-10">
          {/* The work column, sticky - not the reasoning column beside it. At 60/40 the
              reasoning column (long prose, the full requirement list) is reliably the
              taller of the two, so it is also the taller of the row: a sticky element
              cannot float above a sibling once its own box is the one setting the row's
              height, so it never actually detaches from the flow. The work column stays
              the shorter one, so pinning it keeps the action the step is waiting on in
              view while the long diagnosis scrolls past beside it - the reverse of the
              role each column held before the split favoured the reasoning column. */}
          <div className="flex min-w-0 flex-col gap-6 lg:sticky lg:top-20 lg:flex-1 lg:basis-2/5">
            {/* The one thing to do now: run the analysis, resolve the open decisions, or
                generate the draft and move to the editor. */}
            <VerificationStage detail={detail} hasRecommendation={hasRecommendation} onQueued={onQueued} plan={plan} />

            {/* A voluntary configuration edit is a different intent from resolving a review
                blocker even though both currently reach the same backend command. While this
                screen already owns a required decision, its form is the single commit surface;
                otherwise this section is the explicit entry for changing a settled context.
                The CAS source pair is also the local form's lifetime: a changed pair remounts
                the editor before older local choices can be submitted against the new pair. */}
            {classification === null ? null : (
              <MatchingConfigurationEditor
                classification={classification}
                detail={detail}
                onSaved={setMatchingSaved}
                key={`${detail.active_analysis_id ?? "none"}:${detail.active_selection_plan_id ?? "none"}`}
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

            {/* Adjusting which facts the CV carries is a refinement of the generate step, not a
                parallel destination - offered where it is done. */}
            {selectionPlanAction === null ? null : (
              <SelectionPlanPanel action={selectionPlanAction} detail={detail} onQueued={onQueued} />
            )}
          </div>

          {/* The reasoning behind the verdict, for a reader who wants to check it before
              acting. It decides nothing; the acceptance controls it once held are in the
              work column beside it - see that column's own comment for why it, not this
              one, is the sticky side of the row. */}
          {classification === null ? null : (
            <div className="flex min-w-0 flex-col gap-6 lg:flex-1 lg:basis-3/5">
              <AnalysisStage classification={classification} detail={detail} onQueued={onQueued} plan={plan} />
            </div>
          )}
        </div>
      </WideRow>
    </div>
  );
};
