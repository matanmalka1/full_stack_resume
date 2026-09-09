import { useLocation } from "react-router-dom";

import type { ApplicationDetail } from "@/api/contracts";
import { type WorkflowStep, WorkflowStepsRail } from "./WorkflowStepsRail";
import {
  type StageDestinations,
  type WorkflowStage,
  stageForPreparationState,
  workflowDestinations,
  workflowStageHints,
  workflowStageLabels,
  workflowStages,
} from "../model/workflowStages";

/* Where the work stands, for a screen that is part of preparing one Application's CV.

   The position is a prop rather than shell state. It used to be published into a context
   the shell owned, but the bar renders inside `PageShell` - the page's own component - so
   the context carried a page's claim to a component that same page renders. A screen
   outside the workflow now shows no landmark by rendering none, instead of publishing
   `none` to reset what the previous screen left behind. */
interface PreparationWorkflowStepsProps {
  /* Absent while the record naming the Application has not loaded: no stage has a
     destination yet, so the bar is an indicator until one does. */
  applicationId?: string;
  /* Absent while the projection is in flight. The stage the work is on is the
     projection's to state, not this component's to guess, so no stage is marked. */
  detail?: ApplicationDetail;
  /* The stage to mark current, stated rather than derived. The intake step has no
     projection to read it from - the Application does not exist yet - so the create screen
     names its own position. When given, it overrides what `detail` would imply. */
  stage?: WorkflowStage;
}

const stepsFor = (stage: WorkflowStage | undefined, destinations: StageDestinations): WorkflowStep[] => {
  const current = stage === undefined ? -1 : workflowStages.indexOf(stage);
  /* `ready` completes its own stage: everything is done, so nothing is in progress. An
     unknown stage completes nothing - with intake off the bar there is no stage an
     Application is past merely by existing. */
  const completed = stage === undefined ? 0 : stage === "ready" ? current + 1 : current;

  return workflowStages.map((entry, index) => {
    const state = index < completed ? "complete" : index === current ? "current" : "upcoming";

    return {
      label: workflowStageLabels[entry],
      state,
      /* Never forward. The current stage is included because "current" is a position in
         the projection, not a claim about which screen is open: at `ready_for_approval`
         read from the preparation screen, טיוטה ואימות is current and its screen is the
         editor, one the reader is not on. A future stage has no record to open. */
      ...(state !== "upcoming" && destinations[entry] !== undefined ? { href: destinations[entry] } : {}),
    };
  });
};

export const PreparationWorkflowSteps = ({ applicationId, detail, stage: stageOverride }: PreparationWorkflowStepsProps) => {
  const { pathname } = useLocation();

  const stage =
    stageOverride ?? (detail === undefined ? undefined : stageForPreparationState[detail.preparation_state]);
  const destinations = applicationId === undefined ? {} : workflowDestinations(applicationId, detail);
  const steps = stepsFor(stage, destinations);

  /* Which of the three stages the open screen belongs to, found by matching a stage's
     destination against the open path. The current stage wins a tie where one arises. */
  const currentHere = steps.findIndex((step) => step.state === "current" && step.href === pathname);
  const hereIndex = currentHere !== -1 ? currentHere : steps.findIndex((step) => step.href === pathname);

  /* A stage whose screen is the one being read is not a way back. */
  const located = steps.map((step, index) => ({
    ...(index === hereIndex ? { here: true } : {}),
    ...(step.href === pathname ? {} : { href: step.href }),
    label: step.label,
    state: step.state,
  }));

  /* The hint describes the screen the reader is on where that is one of the three, and
     falls back to the stage the work is on where it is not - a revision opened from
     outside the workflow, say. */
  const hintStage = hereIndex === -1 ? stage : workflowStages[hereIndex];

  return (
    <WorkflowStepsRail
      hint={hintStage === undefined ? undefined : workflowStageHints[hintStage]}
      label="שלבי הכנת קורות החיים"
      steps={located}
    />
  );
};
