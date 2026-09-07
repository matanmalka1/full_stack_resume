import { Fragment } from "react";

import { CheckCircle2 } from "lucide-react";
import { Link } from "react-router-dom";

import { surfaceClasses } from "@/ui/surface";
import { cx } from "@/ui/cx";

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

/* The connector entering each step says whether that milestone has been reached. The
   dotted future remains distinct in greyscale; a solid success/accent connector never
   makes an upcoming stage look available. */
const trackClasses: Record<WorkflowStepState, string> = {
  complete: "bg-cv-success",
  current: "bg-cv-accent",
  upcoming: "workflow-track-upcoming",
};

const markClasses: Record<WorkflowStepState, string> = {
  complete: "border-cv-success bg-cv-success-soft text-cv-success",
  /* Current carries a second, wider ring on top of its own border. The ring is what
     makes this the one mark the eye lands on first in a row of otherwise same-size
     circles - the accent fill alone read as "different colour" before it read as
     "here". */
  current:
    "border-cv-accent bg-cv-accent text-cv-on-accent shadow-surface ring-2 ring-cv-accent-soft ring-offset-2 ring-offset-cv-surface",
  upcoming: "border-cv-border bg-cv-canvas text-cv-text-muted",
};

interface WorkflowStepsRailProps {
  /* One line on what the current stage produces. The stage names are single nouns -
     "אימות", "מוכן" - and a noun alone does not say what the stage is for. */
  hint?: string;
  label: string;
  steps: WorkflowStep[];
}

const railClasses = surfaceClasses("w-full min-w-0 bg-cv-surface px-3 py-2.5 shadow-surface");

/* Complete is a check while current and upcoming retain their ordinal. The mark therefore
   communicates state without colour and keeps the compact rail readable as a sequence. */
const StepMark = ({ index, state }: { index: number; state: WorkflowStepState }) => {
  const mark =
    state === "complete" ? (
      <span
        aria-hidden="true"
        className={`relative flex size-9 shrink-0 items-center justify-center rounded-pill border transition-colors duration-200 ${markClasses[state]}`}
      >
        <CheckCircle2 className="size-4" />
      </span>
    ) : (
      <span
        aria-hidden="true"
        className={`relative flex size-9 shrink-0 items-center justify-center rounded-pill border text-support font-bold transition-colors duration-200 ${markClasses[state]}`}
      >
        {index + 1}
      </span>
    );

  if (state !== "current") {
    return mark;
  }

  return (
    <span className="relative inline-flex shrink-0">
      {/* Decorative only: the mark's own ring and fill already say "current" without it
          (A.2, colour is never the only signal). This is the one moment of motion in
          the rail, spent on the single fact worth noticing at a glance - which of the
          three stops the work is standing on right now. */}
      <span
        aria-hidden="true"
        className="absolute inset-0 rounded-pill bg-cv-accent-soft motion-safe:animate-[cv-beacon_2.4s_ease-in-out_infinite]"
      />
      {mark}
    </span>
  );
};

const StepBody = ({
  finalCompletion,
  index,
  step,
}: {
  finalCompletion: boolean;
  index: number;
  step: WorkflowStep;
}) => (
  <span
    className={cx(
      "flex min-w-0 items-center gap-2 rounded-control px-2 py-1.5 text-start transition-[background-color,box-shadow,transform] duration-200",
      step.here === true ? "bg-cv-accent-soft/70" : "",
      /* The lift is the click affordance: text-underline-on-hover said "this is a link"
         only to someone already reading closely, so the whole chip now answers a
         pointer resting on it, not just the label under it. */
      step.href === undefined ? "" : "group-hover:shadow-surface motion-safe:group-hover:-translate-y-0.5",
    )}
  >
    <StepMark index={index} state={step.state} />
    <span className="flex min-w-0 flex-col gap-0.5">
      <span
        className={cx(
          "whitespace-nowrap text-support",
          finalCompletion ? "font-bold text-cv-success" : stateClasses[step.state],
          step.href === undefined ? "" : "group-hover:text-cv-text group-hover:underline",
        )}
      >
        {step.label}
      </span>
      {step.here === true ? (
        <span className="inline-flex w-fit items-center rounded-pill bg-cv-surface px-1.5 py-0.5 text-[0.75rem] font-medium text-cv-text-muted">
          העמוד הפתוח
        </span>
      ) : null}
    </span>
  </span>
);

/* A.1: the landmark shows completed, current, and future stages.

   Two markups, because the honest answer differs. With nothing to go back to it is an
   indicator: `role="img"` with a text alternative, read as "שלב 2 מתוך 3, טיוטה ואימות" rather
   than as a list of destinations that refuse to open. Once a completed stage can be
   opened it is a navigation landmark, and announcing it as one is what tells a screen
   reader the way back exists. The steps that are not links stay hidden from assistive
   technology in both, since the group's own sentence already states the position.

   It sits directly above the primary page surface and shares its width. */
export const WorkflowStepsRail = ({ hint, label, steps }: WorkflowStepsRailProps) => {
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
    <div className="overflow-x-auto pb-1">
      <div className="flex min-w-[30rem] items-center">
        {steps.map((step, index) => {
          const finalCompletion = completed && index === steps.length - 1;
          const body = <StepBody finalCompletion={finalCompletion} index={index} step={step} />;
          const next = steps[index + 1];

          return (
            <Fragment key={step.label}>
              {step.href === undefined ? (
                <div aria-hidden="true" className="min-w-0 flex-1">
                  {body}
                </div>
              ) : (
                <Link
                  /* "חזרה" only where it is true. The current stage is a link when its
                     screen is not the one open, and calling that a way back would
                     misname it. */
                  aria-current={step.state === "current" ? "step" : undefined}
                  aria-label={
                    finalCompletion
                      ? `פתיחת שלב ${step.label}`
                      : `${step.state === "complete" ? "חזרה" : "מעבר"} לשלב ${step.label}`
                  }
                  className="group min-w-0 flex-1 rounded-control"
                  to={step.href}
                >
                  {body}
                </Link>
              )}
              {next === undefined ? null : (
                <span
                  aria-hidden="true"
                  className={cx(
                    "h-1 min-w-6 flex-1 rounded-pill transition-colors duration-200",
                    trackClasses[next.state],
                  )}
                />
              )}
            </Fragment>
          );
        })}
      </div>
    </div>
  );

  if (!navigable) {
    return (
      <div aria-label={description} className={railClasses} role="img">
        {/* Hidden from assistive technology entirely: the group above already states the
            position in one sentence, and reading the segment labels after it says the
            same thing a second time, worse. */}
        <div aria-hidden="true">
          {heading}
          {row}
        </div>
      </div>
    );
  }

  return (
    <nav aria-label={description} className={railClasses}>
      {heading}
      {row}
    </nav>
  );
};
