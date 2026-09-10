import { ArrowRight } from "lucide-react";
import { Link, useLocation } from "react-router-dom";

import type { ApplicationDetail } from "@/api/contracts";
import { boardPath } from "@/app/boardReturn";
import { type WorkflowStep, WorkflowStepsRail } from "./WorkflowStepsRail";
import {
  type StageDestinations,
  type WorkflowStage,
  stageForPreparationState,
  workflowDestinations,
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
  /* Read only for which steps *ahead* of the current one already show a checkmark - a
     stage reached by revisiting an earlier screen. It never moves the current chip. */
  detail?: ApplicationDetail;
  /* The stage to mark current, stated by the open screen rather than read from the
     projection: the screen open is a fact the reader can see, and the chip must agree with
     it even while the projection is mid-refetch. */
  stage: WorkflowStage;
}

const stepsFor = (
  stage: WorkflowStage,
  detail: ApplicationDetail | undefined,
  destinations: StageDestinations,
): WorkflowStep[] => {
  const current = workflowStages.indexOf(stage);
  const projectionStage = detail === undefined ? undefined : stageForPreparationState[detail.preparation_state];
  const projectionIndex = projectionStage === undefined ? -1 : workflowStages.indexOf(projectionStage);
  /* Never below `current`: the screen open is at least that far along regardless of what a
     transient projection dip reports mid-edit. May sit above `current` when the projection
     is ahead of the screen the reader chose to revisit - that only raises earlier chips to
     "complete", never the open screen's own chip (below). */
  const completed = Math.max(current, projectionStage === "ready" ? projectionIndex + 1 : projectionIndex);

  return workflowStages.map((entry, index) => {
    /* The open screen's own chip is never read off `completed`: it would otherwise flip to
       "complete" the moment the projection runs ahead of the screen the reader is on, and
       leave nothing marked "current" at all. `ready` is the one stage where being on the
       screen already means everything, including it, is done. */
    const state: WorkflowStep["state"] =
      index === current ? (stage === "ready" ? "complete" : "current") : index < completed ? "complete" : "upcoming";

    return Object.assign(
      { label: workflowStageLabels[entry], state },
      /* Never forward. A future stage has no record to open. */
      state !== "upcoming" && destinations[entry] !== undefined ? { href: destinations[entry] } : {},
    );
  });
};

export const PreparationWorkflowSteps = ({ applicationId, detail, stage }: PreparationWorkflowStepsProps) => {
  const { pathname } = useLocation();

  const destinations = applicationId === undefined ? {} : workflowDestinations(applicationId, detail);
  const steps = stepsFor(stage, detail, destinations);

  /* Which of the three stages the open screen belongs to, found by matching a stage's
     destination against the open path. The current stage wins a tie where one arises. */
  const currentHere = steps.findIndex((step) => step.state === "current" && step.href === pathname);
  const hereIndex = currentHere !== -1 ? currentHere : steps.findIndex((step) => step.href === pathname);

  /* A stage whose screen is the one being read is not a way back. */
  const located = steps.map((step, index) =>
    Object.assign(
      { label: step.label, state: step.state },
      index === hereIndex ? { here: true } : {},
      step.href === pathname ? {} : { href: step.href },
    ),
  );

  /* One way out, above the spine, and the wizard's only navigation besides it.

     The flow screens used to carry a breadcrumb trail as well - board › Application ›
     editor - which drew a record hierarchy over a linear piece of work and gave the reader
     two navigation landmarks saying different things about the same position. The trail's
     only unique destination was the board, so that is what is left: a way out of the
     wizard, not a level above it. It returns to the board as the reader left it, filters
     and all. */
  return (
    <div className="flex flex-col gap-2">
      <Link
        className="inline-flex min-h-11 w-fit items-center gap-1.5 rounded-control px-1 text-support font-semibold text-cv-text-muted transition-colors duration-200 hover:text-cv-text"
        to={boardPath()}
      >
        <ArrowRight aria-hidden="true" className="size-icon-md shrink-0" />
        חזרה ללוח המועמדויות
      </Link>

      <WorkflowStepsRail label="שלבי הכנת קורות החיים" steps={located} />
    </div>
  );
};
