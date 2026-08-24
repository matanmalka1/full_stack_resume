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

/* `intake` is the screen that exists before an Application does. `unknown` is an
   Application whose projection has not arrived yet, which is a different thing: its
   intake is behind it, but the stage it is on is not this module's to guess. */
export type WorkflowStage = PreparationState | "intake" | "unknown";

export const workflowStepsFor = (stage: WorkflowStage): WorkflowStep[] => {
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

/* The landmark is a shell region (A.1) but the projection belongs to the page, so the
   page states the stage rather than the shell inferring it from the URL. A screen that
   reads no projection publishes nothing and leaves the intake default in place. */
export const WorkflowLandmark = ({ children }: { children: ReactNode }) => {
  const [stage, setStage] = useState<WorkflowStage>("intake");

  return (
    <WorkflowStageContext.Provider value={setStage}>
      <WorkflowSteps label="שלבי הכנת קורות החיים" steps={workflowStepsFor(stage)} />
      {children}
    </WorkflowStageContext.Provider>
  );
};

export const useWorkflowStage = (stage: WorkflowStage): void => {
  const publish = useContext(WorkflowStageContext);

  useEffect(() => {
    publish?.(stage);
    /* Leaving the screen takes its claim with it, so a landmark can never outlive the
       projection that produced it. */
    return () => publish?.("intake");
  }, [publish, stage]);
};
