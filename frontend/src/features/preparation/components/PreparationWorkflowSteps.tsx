import { ArrowRight, ChevronRight, X } from "lucide-react";
import type { ReactNode } from "react";
import { Link, useLocation } from "react-router-dom";

import type { ApplicationDetail } from "@/api/contracts";
import { boardPath, boardReturnState } from "@/navigation/boardReturn";
import { cx } from "@/ui/cx";
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
/* What a step adds to its compact header on a phone. Every part is optional: a step that
   passes nothing gets the role as its title, the company under it and the stage bar. */
export interface PhoneHeader {
  /* One trailing control - an overflow menu, the draft's preview toggle. Rendered below
     the large breakpoint only, so it must not repeat a control the step already shows on
     a phone. Give it a 44px target and an accessible name; it is usually icon-only. */
  action?: ReactNode;
  /* Whether the stage bar is drawn under the title. A step whose own body already says
     where the work stands (the Application's checklist) can drop it. Default true. */
  bar?: boolean;
  /* Leads the title with the company's initial in a tile, as the Application screen's
     design does. */
  mark?: boolean;
  /* Replace the default subtitle (the company) or title (the role). */
  subtitle?: ReactNode;
  title?: ReactNode;
}

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
  phoneHeader?: PhoneHeader;
}

const NO_PHONE_HEADER: PhoneHeader = {};

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
      /* A destination exists only when the corresponding record exists. The projection
         may still draw that stage as upcoming relative to the screen being revisited, but
         hiding its destination would make an existing draft reachable from the board and
         its direct URL while inexplicably unreachable from this workflow landmark. */
      destinations[entry] !== undefined ? { href: destinations[entry] } : {},
    );
  });
};

export const PreparationWorkflowSteps = ({
  applicationId,
  detail,
  phoneHeader = NO_PHONE_HEADER,
  stage,
}: PreparationWorkflowStepsProps) => {
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
  /* On a phone the step's top is the compact header an app's inner screen has: the way out
     as a chevron, who the CV is for as the title, an optional trailing action, and the
     stage bar under them. The new-job screen draws the way out as a close mark instead -
     nothing has been created yet, so leaving is cancelling rather than going back - and
     keeps its numbered stepper under the page's own heading. The link's name is the same
     words either way. */
  const intake = stage === "intake";
  const company = detail?.application.company;
  const role = detail?.application.target_role;
  const title = phoneHeader.title ?? role ?? workflowStageLabels[stage];
  const subtitle = phoneHeader.subtitle ?? company;
  const initial = company?.trim().charAt(0);

  return (
    <div
      className={cx(
        "flex flex-col gap-2",
        !intake &&
          "max-lg:grid max-lg:grid-cols-[auto_minmax(0,1fr)_auto] max-lg:items-center max-lg:gap-x-2 max-lg:gap-y-3",
      )}
    >
      <Link
        className="inline-flex min-h-11 w-fit shrink-0 items-center gap-1.5 rounded-control px-1 text-support font-semibold text-cv-text-muted transition-colors duration-200 hover:text-cv-text max-lg:min-w-11 max-lg:justify-center max-lg:px-0 max-lg:text-cv-text"
        state={boardReturnState(applicationId)}
        to={boardPath()}
      >
        <ArrowRight aria-hidden="true" className="size-icon-md shrink-0 max-lg:hidden" />
        {intake ? (
          <X aria-hidden="true" className="size-icon-lg shrink-0 lg:hidden" />
        ) : (
          <ChevronRight aria-hidden="true" className="size-icon-lg shrink-0 lg:hidden" />
        )}
        <span className="max-lg:sr-only">חזרה ללוח המועמדויות</span>
      </Link>

      {/* Drawn for sighted readers only: the page's heading and its eyebrow, which say the
          same in words, stay in the document for assistive tech and route focus. */}
      {intake ? null : (
        <div aria-hidden="true" className="flex min-w-0 items-center gap-3 lg:hidden">
          {phoneHeader.mark === true && initial !== undefined && initial !== "" ? (
            <span
              className="flex size-12 shrink-0 items-center justify-center rounded-surface border border-cv-border bg-cv-surface text-heading-sm font-extrabold text-cv-text"
              dir="auto"
            >
              {initial}
            </span>
          ) : null}
          <span className="flex min-w-0 flex-col">
            <span className="truncate text-heading-sm leading-6 font-extrabold text-cv-text" dir="auto">
              {title}
            </span>
            {subtitle === undefined ? null : (
              <span className="truncate text-support text-cv-text-muted" dir="auto">
                {subtitle}
              </span>
            )}
          </span>
        </div>
      )}
      {intake || phoneHeader.action === undefined ? null : (
        <div className="flex shrink-0 items-center lg:hidden">{phoneHeader.action}</div>
      )}

      <div className={cx(!intake && "max-lg:col-span-3", phoneHeader.bar === false && "max-lg:hidden")}>
        <WorkflowStepsRail label="שלבי הכנת קורות החיים" phone={intake ? "marks" : "segments"} steps={located} />
      </div>
    </div>
  );
};
