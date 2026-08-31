import { createContext, type ReactNode, useContext, useEffect, useState } from "react";

import type { PreparationState } from "../api/contracts";
import { type WorkflowStep, WorkflowSteps } from "../ui/WorkflowSteps";

/* A.4 frame 1 region 3: five ordered stages, and the only place their Hebrew names
   live. */
const stages = ["intake", "analysis", "draft", "validation", "ready"] as const;

type Stage = (typeof stages)[number];

const stageLabels: Record<Stage, string> = {
  intake: "משרה חדשה",
  analysis: "ניתוח",
  draft: "טיוטה",
  validation: "אימות",
  ready: "מוכן",
};

/* Where the backend's PreparationState sits in the landmark. Exhaustive over the
   generated union, so a state added to the projection fails the build here rather than
   leaving the landmark on whichever stage it happened to be showing.

   This is a display position, not a second workflow state machine (A.1). It decides
   nothing: what may happen next comes from `available_actions` and `recommended_action`,
   and no stage is navigable. */
const stageForPreparationState: Record<PreparationState, Stage> = {
  needs_analysis: "analysis",
  needs_review: "analysis",
  ready_to_draft: "draft",
  draft_in_progress: "draft",
  ready_for_approval: "validation",
  approved: "ready",
  ready: "ready",
};

/* Three kinds of screen, not two.

   `intake` is the screen that exists before an Application does. `unknown` is an
   Application whose projection has not arrived yet, which is a different thing: its
   intake is behind it, but the stage it is on is not this module's to guess.

   `none` is a screen standing outside the workflow altogether - Settings, a not-found
   route - where no stage is the honest answer and the landmark has nothing to report. */
export type WorkflowStage = PreparationState | "intake" | "none" | "unknown";

/* `none` never reaches here: the landmark renders no steps at all for it, rather than a
   row of five in which every one is `upcoming`. Every other stage keeps its exact
   behavior. */
export const workflowStepsFor = (stage: Exclude<WorkflowStage, "none">): WorkflowStep[] => {
  const current =
    stage === "intake"
      ? 0
      : stage === "unknown"
        ? -1
        : stages.indexOf(stageForPreparationState[stage]);
  /* `ready` completes its own stage: everything is done, so nothing is in progress.
     `unknown` completes only the intake it is certainly past. */
  const completed = stage === "unknown" ? 1 : stage === "ready" ? current + 1 : current;

  return stages.map((stage_, index) => ({
    label: stageLabels[stage_],
    state: index < completed ? "complete" : index === current ? "current" : "upcoming",
  }));
};

const WorkflowStageContext = createContext<((stage: WorkflowStage) => void) | undefined>(undefined);
const WorkflowStageValueContext = createContext<WorkflowStage>("intake");

/* The landmark is a shell region (A.1) but the projection belongs to the page, so the
   page states the stage rather than the shell inferring it from the URL.

   Publishing is mandatory, because the claim is no longer reset on unmount: a route that
   says nothing inherits whatever the previous screen left behind. Each of the three kinds
   says its own - an Application route its `PreparationState`, the intake screen `intake`,
   and a screen outside the workflow `none`. */
export const WorkflowLandmark = ({ children }: { children: ReactNode }) => {
  const [stage, setStage] = useState<WorkflowStage>("intake");

  return (
    <WorkflowStageValueContext.Provider value={stage}>
      <WorkflowStageContext.Provider value={setStage}>{children}</WorkflowStageContext.Provider>
    </WorkflowStageValueContext.Provider>
  );
};

/* Split from the provider so the shell can place the steps above the page surface while
   the stage itself still comes from the page rendered below it. */
export const WorkflowLandmarkSteps = () => {
  const stage = useContext(WorkflowStageValueContext);

  /* Off-workflow screens get no landmark rather than a stale one. Without this, removing
     the unmount reset would leave Settings showing whichever stage the previous screen
     published - the breadcrumb still claiming "אימות" while the user is in Settings. */
  if (stage === "none") {
    return null;
  }

  return <WorkflowSteps label="שלבי הכנת קורות החיים" steps={workflowStepsFor(stage)} />;
};

export const useWorkflowStage = (stage: WorkflowStage): void => {
  const publish = useContext(WorkflowStageContext);

  useEffect(() => {
    publish?.(stage);
    /* No reset on unmount. Resetting here produced a flash of `intake` between two
       screens that were both mid-workflow - the landmark appearing to restart while the
       user moved from the editor to the operation it queued.

       That makes publishing mandatory rather than optional: a screen that publishes
       nothing now inherits the stage the previous one left behind. Every route states
       its own answer, including `intake` and `none`. */
  }, [publish, stage]);
};
