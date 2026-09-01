import { Link } from "react-router-dom";

import { cx } from "./cx";

type WorkflowStepState = "complete" | "current" | "upcoming";

export interface WorkflowStep {
  /* Set on a stage the projection has reached, where its record exists and its screen is
     not the one being read. Absent means the step is an indicator and nothing more. */
  href?: string;
  label: string;
  state: WorkflowStepState;
}

const stateClasses: Record<WorkflowStepState, string> = {
  complete: "text-cv-text-muted",
  current: "font-bold text-cv-accent",
  /* The muted token already carries the hierarchy. Applying opacity on top blended it
     into the header surface at 3.09:1, below the 4.5:1 required for this 14px label. */
  upcoming: "text-cv-text-muted",
};

/* The track each step draws under its own label: a filled segment for what is done, the
   accent for where the work is, a hairline for what is ahead.

   It replaced a row of numbered circles - filled discs, a checkmark, connecting rules -
   which is the visual language of a wizard whose every step is pressable. Forward is
   still not a place: which action is possible is the projection's answer, so a stage it
   has not reached opens nothing. What it has reached does have a screen, so those steps
   are links and the rest are not - and the bar keeps reading as progress rather than as
   five buttons of which some ignore you. */
const trackClasses: Record<WorkflowStepState, string> = {
  complete: "bg-cv-success",
  current: "bg-cv-accent",
  upcoming: "bg-cv-border",
};

interface WorkflowStepsProps {
  label: string;
  steps: WorkflowStep[];
}

/* Below md the row keeps the current step and whatever can be reached from it. Hiding the
   completed steps there would remove the back gesture at exactly the width where it is
   hardest to replace. */
const visibilityClasses = (step: WorkflowStep) =>
  step.state === "current" || step.href !== undefined ? "flex" : "hidden md:flex";

const StepBody = ({ step }: { step: WorkflowStep }) => (
  <>
    <span
      className={cx(
        "whitespace-nowrap text-support",
        stateClasses[step.state],
        step.href === undefined ? "" : "group-hover:text-cv-text group-hover:underline",
      )}
    >
      {step.label}
    </span>
    <span className={cx("h-0.5 w-full min-w-8 rounded-pill md:min-w-10 lg:min-w-14", trackClasses[step.state])} />
  </>
);

/* A.1: the landmark shows completed, current, and future stages.

   Two markups, because the honest answer differs. With nothing to go back to it is an
   indicator: `role="img"` with a text alternative, read as "שלב 2 מתוך 5, ניתוח" rather
   than as a list of five destinations that refuse to open. Once a completed stage can be
   opened it is a navigation landmark, and announcing it as one is what tells a screen
   reader the way back exists. The steps that are not links stay hidden from assistive
   technology in both, since the group's own sentence already states the position.

   It sits directly above the primary page surface and shares its width. */
export const WorkflowSteps = ({ label, steps }: WorkflowStepsProps) => {
  const current = steps.find((step) => step.state === "current");
  const position = current === undefined ? null : steps.indexOf(current) + 1;
  /* One sentence for anyone not reading the bar, which is also the whole of what the bar
     says: where the work is, and out of how many stages. */
  const description = position === null ? label : `${label}: שלב ${position} מתוך ${steps.length}, ${current?.label}`;
  const navigable = steps.some((step) => step.href !== undefined);

  const row = (
    <div className="flex items-end gap-1.5 md:gap-2">
      {steps.map((step) =>
        step.href === undefined ? (
          <div
            aria-hidden="true"
            className={cx("min-w-0 flex-1 flex-col gap-1.5", visibilityClasses(step))}
            key={step.label}
          >
            <StepBody step={step} />
          </div>
        ) : (
          <Link
            /* "חזרה" only where it is true. The current stage is a link when its screen is
               not the one open, and calling that a way back would misname it. */
            aria-current={step.state === "current" ? "step" : undefined}
            aria-label={`${step.state === "complete" ? "חזרה" : "מעבר"} לשלב ${step.label}`}
            className={cx("group min-w-0 flex-1 flex-col gap-1.5 rounded-control", visibilityClasses(step))}
            key={step.label}
            to={step.href}
          >
            <StepBody step={step} />
          </Link>
        ),
      )}
    </div>
  );

  if (!navigable) {
    return (
      <div aria-label={description} className="w-full min-w-0" role="img">
        {/* Hidden from assistive technology entirely: the group above already states the
            position in one sentence, and reading five segment labels after it says the
            same thing a second time, worse. */}
        <div aria-hidden="true">{row}</div>
      </div>
    );
  }

  return (
    <nav aria-label={description} className="w-full min-w-0">
      {row}
    </nav>
  );
};
