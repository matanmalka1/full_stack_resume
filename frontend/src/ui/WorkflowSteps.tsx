import { cx } from "./cx";

type WorkflowStepState = "complete" | "current" | "upcoming";

export interface WorkflowStep {
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
   which is the visual language of a wizard whose steps are pressed. None of the five is a
   route: no stage can be opened, because which action is possible is the projection's
   answer and not a place to navigate to. So the indicator no longer offers what it cannot
   honour. A bar reads as progress; a numbered disc reads as a button that is ignoring
   you. */
const trackClasses: Record<WorkflowStepState, string> = {
  complete: "bg-cv-success",
  current: "bg-cv-accent",
  upcoming: "bg-cv-border",
};

interface WorkflowStepsProps {
  label: string;
  steps: WorkflowStep[];
}

/* A.1: the landmark shows completed, current, and future stages.

   No stage is navigable, and the markup now says so. It is a `<p>`-led group rather than
   a `<nav>`: a navigation landmark announces "here is a way to move around" to a screen
   reader, and there is nothing in here to move to. `role="img"` with a text alternative
   is what an indicator is - one thing that reports a position - so it is read as
   "שלב 2 מתוך 5, ניתוח" instead of as a list of five destinations that refuse to open.

   It sits directly above the primary page surface and shares its width. Narrow widths
   keep only the current step, which is the "current-step summary" A.4 frame 4 asks for. */
export const WorkflowSteps = ({ label, steps }: WorkflowStepsProps) => {
  const current = steps.find((step) => step.state === "current");
  const position = current === undefined ? null : steps.indexOf(current) + 1;
  /* One sentence for anyone not reading the bar, which is also the whole of what the bar
     says: where the work is, and out of how many stages. */
  const description = position === null ? label : `${label}: שלב ${position} מתוך ${steps.length}, ${current?.label}`;

  return (
    <div aria-label={description} className="w-full min-w-0" role="img">
      {/* Hidden from assistive technology entirely: the group above already states the
          position in one sentence, and reading five segment labels after it says the same
          thing a second time, worse. */}
      <div aria-hidden="true" className="flex items-end gap-1.5 md:gap-2">
        {steps.map((step) => (
          <div
            className={cx(
              "min-w-0 flex-1 flex-col gap-1.5",
              /* Below md only the current step is shown, keeping the indicator compact
                 while its track still fills the available width. */
              step.state === "current" ? "flex" : "hidden md:flex",
            )}
            key={step.label}
          >
            <span className={cx("whitespace-nowrap text-support", stateClasses[step.state])}>{step.label}</span>
            <span
              className={cx("h-0.5 w-full min-w-8 rounded-pill md:min-w-10 lg:min-w-14", trackClasses[step.state])}
            />
          </div>
        ))}
      </div>
    </div>
  );
};
