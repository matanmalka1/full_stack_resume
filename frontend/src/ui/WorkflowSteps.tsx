import { Fragment } from "react";

import { Check } from "lucide-react";
import { Link } from "react-router-dom";

import { cx } from "./cx";

type WorkflowStepState = "complete" | "current" | "upcoming";

export interface WorkflowStep {
  /* The stage whose screen is the one open. A separate fact from `state`: `current` is
     where the work is, which is regularly not where the reader is - at
     `ready_for_approval` read from the preparation screen, אימות is current and its
     screen is the editor. Drawing only `current` left the bar answering a question the
     reader had not asked and silent on the one they had. */
  here?: boolean;
  /* Set on a stage the projection has reached, where its record exists and its screen is
     not the one being read. Absent means the step is an indicator and nothing more. */
  href?: string;
  label: string;
  state: WorkflowStepState;
}

/* Three treatments, not two. `complete` used to share the muted token with `upcoming`,
   which left "done" and "not started yet" separated by nothing but the colour of a 2px
   hairline - the whole reason the bar read as five undifferentiated words. Done is now
   plain body text, ahead stays muted, and the mark beside each label carries the same
   distinction without colour (A.2). */
const stateClasses: Record<WorkflowStepState, string> = {
  complete: "text-cv-text",
  current: "font-bold text-cv-accent",
  upcoming: "text-cv-text-muted",
};

/* The track each step draws under its own label: a filled segment for what is done, the
   accent for where the work is, a dotted rule for what is ahead.

   It replaced a row of numbered circles - filled discs, a checkmark, connecting rules -
   which is the visual language of a wizard whose every step is pressable. Forward is
   still not a place: which action is possible is the projection's answer, so a stage it
   has not reached opens nothing. What it has reached does have a screen, so those steps
   are links and the rest are not - and the bar keeps reading as progress rather than as
   five buttons of which some ignore you.

   Upcoming is dotted rather than a paler solid, so the segment says "not laid yet" in
   greyscale too. */
const trackClasses: Record<WorkflowStepState, string> = {
  complete: "bg-cv-success",
  current: "bg-cv-accent",
  upcoming: "workflow-track-upcoming",
};

interface WorkflowStepsProps {
  /* One line on what the current stage produces. The stage names are single nouns -
     "אימות", "מוכן" - and a noun alone does not say what the stage is for. */
  hint?: string;
  label: string;
  steps: WorkflowStep[];
}

/* Below md the row keeps the open step, the current one, and whatever can be reached from
   them. Hiding the completed steps there would remove the back gesture at exactly the
   width where it is hardest to replace, and hiding the open one would drop the "you are
   here" mark on the widths that need it most. The position line above carries the count
   that the shortened row can no longer show. */
const visibilityClasses = (step: WorkflowStep) =>
  step.here === true || step.state === "current" || step.href !== undefined ? "flex" : "hidden md:flex";

/* Complete is a check, current a filled dot, upcoming nothing. Redundant with the colour
   rather than decorative: it is what survives a greyscale print or a reader who cannot
   separate the green track from the grey one. */
const StepMark = ({ state }: { state: WorkflowStepState }) => {
  if (state === "complete") {
    return <Check aria-hidden="true" className="size-3.5 shrink-0 text-cv-success" />;
  }

  if (state === "current") {
    return <span aria-hidden="true" className="size-1.5 shrink-0 rounded-pill bg-cv-accent" />;
  }

  return null;
};

const StepBody = ({ finalCompletion, step }: { finalCompletion: boolean; step: WorkflowStep }) => (
  <>
    <span className="flex min-w-0 items-center gap-1">
      <StepMark state={step.state} />
      <span
        className={cx(
          "whitespace-nowrap text-support",
          finalCompletion ? "font-bold text-cv-success" : stateClasses[step.state],
          /* The open stage is a filled chip, and the position line above names the same
             stage in the same words. The chip is what ties that sentence to a column, so
             the reader does not have to work out which of five the sentence meant. */
          step.here === true ? "rounded-control bg-cv-accent-soft px-1.5 font-bold text-cv-text" : "",
          step.href === undefined ? "" : "group-hover:text-cv-text group-hover:underline",
        )}
      >
        {step.label}
      </span>
    </span>
    <span className={cx("h-1 w-full min-w-8 rounded-pill md:min-w-10 lg:min-w-14", trackClasses[step.state])} />
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
export const WorkflowSteps = ({ hint, label, steps }: WorkflowStepsProps) => {
  const current = steps.find((step) => step.state === "current");
  const position = current === undefined ? null : steps.indexOf(current) + 1;
  const completed = current === undefined && steps.length > 0 && steps.every((step) => step.state === "complete");
  const here = steps.find((step) => step.here === true);
  /* The open screen is a different fact from where the work stands, and is named
     separately only where the two part: on the analysis screen at `needs_analysis` both
     clauses would say "ניתוח", and a sentence saying one word twice reads as a bug
     rather than as two facts. */
  const elsewhere = here !== undefined && here !== current;
  /* One sentence for anyone not reading the bar, which is the whole of what the bar says:
     which screen this is, where the work stands, and out of how many stages. */
  const spoken = completed
    ? `הושלם, ${steps.length} מתוך ${steps.length}`
    : position === null
      ? null
      : `שלב ${position} מתוך ${steps.length}, ${current?.label}`;
  const description =
    spoken === null
      ? here === undefined
        ? label
        : `${label}: העמוד הפתוח ${here.label}`
      : `${label}: ${spoken}${elsewhere ? `. העמוד הפתוח: ${here.label}` : ""}`;
  const navigable = steps.some((step) => step.href !== undefined);

  /* Where the work stands, for the eye. It repeats the stage name only when that is news
     - when the work is on a stage other than the one being read. */
  const progressText = completed
    ? `הושלם, ${steps.length} מתוך ${steps.length}`
    : position === null
      ? null
      : elsewhere
        ? `העבודה בשלב ${position} מתוך ${steps.length}: ${current?.label}`
        : `שלב ${position} מתוך ${steps.length}`;

  /* Two facts, in the order they are asked for. Which screen this is comes first and in
     the strongest weight, because nothing else in the bar answers it; where the work
     stands follows.

     Each clause is one element holding one string, and the separators sit between them
     rather than inside them - so a clause reads as its own sentence rather than as one
     beginning with a stray bullet.

     Hidden from assistive technology: `description` states the same thing, and hearing it
     twice is worse than hearing it once. */
  const clauses = [
    here === undefined ? null : <span className="font-bold text-cv-text">{`עמוד ${here.label}`}</span>,
    progressText === null ? null : (
      <span className={here === undefined ? "font-bold text-cv-text" : undefined}>{progressText}</span>
    ),
    hint === undefined ? null : <span>{hint}</span>,
  ].filter((clause) => clause !== null);

  const heading = (
    <p aria-hidden="true" className="mb-1.5 truncate text-support text-cv-text-muted">
      {clauses.map((clause, index) => (
        <Fragment key={index}>
          {index === 0 ? null : " · "}
          {clause}
        </Fragment>
      ))}
    </p>
  );

  const row = (
    <div className="flex items-end gap-1.5 md:gap-2">
      {steps.map((step, index) =>
        step.href === undefined ? (
          <div
            aria-hidden="true"
            className={cx("min-w-0 flex-1 flex-col gap-1.5", visibilityClasses(step))}
            key={step.label}
          >
            <StepBody finalCompletion={completed && index === steps.length - 1} step={step} />
          </div>
        ) : (
          <Link
            /* "חזרה" only where it is true. The current stage is a link when its screen is
               not the one open, and calling that a way back would misname it. */
            aria-current={step.state === "current" ? "step" : undefined}
            aria-label={
              completed && index === steps.length - 1
                ? `פתיחת שלב ${step.label}`
                : `${step.state === "complete" ? "חזרה" : "מעבר"} לשלב ${step.label}`
            }
            className={cx("group min-w-0 flex-1 flex-col gap-1.5 rounded-control", visibilityClasses(step))}
            key={step.label}
            to={step.href}
          >
            <StepBody finalCompletion={completed && index === steps.length - 1} step={step} />
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
        <div aria-hidden="true">
          {heading}
          {row}
        </div>
      </div>
    );
  }

  return (
    <nav aria-label={description} className="w-full min-w-0">
      {heading}
      {row}
    </nav>
  );
};
