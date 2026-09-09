import { Fragment } from "react";

import { Check } from "lucide-react";
import { Link } from "react-router-dom";

import { surfaceClasses } from "@/ui/surface";
import { cx } from "@/ui/cx";

type WorkflowStepState = "complete" | "current" | "upcoming";

export interface WorkflowStep {
  here?: boolean;
  href?: string;
  label: string;
  state: WorkflowStepState;
}

interface WorkflowStepsRailProps {
  hint?: string;
  label: string;
  steps: WorkflowStep[];
}

const railClasses = surfaceClasses("w-full min-w-0 overflow-hidden bg-cv-surface shadow-surface");

const stepMarkClasses: Record<WorkflowStepState, string> = {
  complete: "border-cv-success/25 bg-cv-success-soft text-cv-success",
  current: "border-cv-accent bg-cv-accent text-cv-on-accent",
  upcoming: "border-cv-border bg-cv-surface text-cv-text-muted",
};

const stepLabelClasses: Record<WorkflowStepState, string> = {
  complete: "font-semibold text-cv-text",
  current: "font-bold text-cv-accent",
  upcoming: "font-medium text-cv-text-muted",
};

const connectorClasses: Record<WorkflowStepState, string> = {
  complete: "bg-cv-success",
  current: "bg-cv-accent",
  upcoming: "workflow-track-upcoming",
};

const StepMark = ({ index, state }: { index: number; state: WorkflowStepState }) => (
  <span
    aria-hidden="true"
    className={cx(
      "relative z-10 flex size-6 shrink-0 items-center justify-center rounded-pill border",
      "text-[0.6875rem] font-bold transition-[background-color,border-color,color] duration-200",
      stepMarkClasses[state],
    )}
  >
    {state === "complete" ? <Check className="size-3 stroke-[3]" /> : index + 1}
  </span>
);

/* One step: a mark and its label, the whole rail's only content. The state used to carry
   its own caption underneath ("הושלם" / "בתהליך" / "בהמשך") - a second line that made a
   navigational rail read as a content section three rows tall. It was never the only
   place that information lived: a `Link`'s own accessible name already says "חזרה" for a
   completed step and "מעבר" for one still ahead, and `aria-current="step"` already marks
   the current one, so the caption was sighted users' only source for a fact assistive
   tech already had another way to reach. What remains carries the same three states in
   the mark's own shape (a check, a filled circle, an outline) and in the label's weight
   and colour - color is never the only signal (A.2), and it no longer needs to be a
   second line to avoid being one. */
const StepBody = ({ index, step }: { index: number; step: WorkflowStep }) => (
  <span
    className={cx(
      "relative flex shrink-0 items-center gap-2 rounded-pill px-2.5 py-1.5 text-support transition-colors duration-200",
      stepLabelClasses[step.state],
      step.state === "current" && "bg-cv-accent-soft/55",
      step.here === true && step.state !== "current" && "bg-cv-surface-muted",
      step.href !== undefined && "group-hover:bg-cv-surface-muted",
    )}
  >
    <StepMark index={index} state={step.state} />
    <span className="whitespace-nowrap">{step.label}</span>
  </span>
);

/* Orientation, not a page section: which of the three stages the work is on, in one
   compact row a reader passes on the way to the content that actually needs the space.
   It used to spend a header band and a full row of large cards to say what the row below
   now says by itself - three marks, three labels, and the line between them. */
export const WorkflowStepsRail = ({ hint, label, steps }: WorkflowStepsRailProps) => {
  const current = steps.find((step) => step.state === "current");
  const position = current === undefined ? null : steps.indexOf(current) + 1;
  const completed = current === undefined && steps.length > 0 && steps.every((step) => step.state === "complete");
  const here = steps.find((step) => step.here === true);
  const elsewhere = here !== undefined && here !== current;

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

  /* Led by a Hebrew word rather than a bare digit. Two number runs with nothing but
     Hebrew between them still read correctly in an RTL paragraph, but a number run at
     the very start of one does not carry the paragraph's own direction the way a Hebrew
     word does - left as `"2 מתוך 3"` with no anchor before the "2", browsers have shown
     the pair transposed ("3 מתוך 2"). A leading word fixes the embedding, same as the
     screen-reader sentence above already has one. */
  const progressText = completed
    ? `הושלם ${steps.length} מתוך ${steps.length}`
    : position === null
      ? null
      : `שלב ${position} מתוך ${steps.length}`;

  const content = (
    <div className="flex flex-wrap items-center gap-x-4 gap-y-1.5 px-3 py-2.5 sm:px-4">
      {/* Decorative: the nav's own `aria-label` already states the label and the
          position in words, so this repeats it for sighted readers only. */}
      <div aria-hidden="true" className="flex shrink-0 items-baseline gap-x-2">
        <span className="text-support font-bold text-cv-text">{label}</span>
        {progressText === null ? null : <span className="text-[0.75rem] text-cv-text-muted">{progressText}</span>}
      </div>

      {/* Scrolls, but shows no bar: the rail is one line tall, and even the page's thin
          scrollbar takes a visible share of that height rather than overlaying it.
          Nothing here is reachable only by scrolling - every step is a link the keyboard
          reaches in order - so hiding the bar hides no content. */}
      <div className="scrollbar-none min-w-0 flex-1 overflow-x-auto">
        <div className="flex w-fit items-center">
          {steps.map((step, index) => {
            const body = <StepBody index={index} step={step} />;
            const next = steps[index + 1];

            return (
              <Fragment key={step.label}>
                {step.href === undefined ? (
                  <div aria-hidden="true">{body}</div>
                ) : (
                  <Link
                    aria-current={step.state === "current" ? "step" : undefined}
                    aria-label={
                      completed && index === steps.length - 1
                        ? `פתיחת שלב ${step.label}`
                        : `${step.state === "complete" ? "חזרה" : "מעבר"} לשלב ${step.label}`
                    }
                    className="group flex min-h-11 items-center rounded-pill"
                    to={step.href}
                  >
                    {body}
                  </Link>
                )}

                {next === undefined ? null : (
                  <span
                    aria-hidden="true"
                    className={cx("mx-1 h-0.5 w-4 shrink-0 rounded-pill sm:w-8", connectorClasses[next.state])}
                  />
                )}
              </Fragment>
            );
          })}
        </div>
      </div>

      {hint === undefined ? null : (
        <p aria-hidden="true" className="hidden max-w-64 shrink-0 truncate text-[0.75rem] text-cv-text-muted lg:block">
          {hint}
        </p>
      )}
    </div>
  );

  if (!navigable) {
    return (
      <div aria-label={description} className={railClasses} role="img">
        <div aria-hidden="true">{content}</div>
      </div>
    );
  }

  return (
    <nav aria-label={description} className={railClasses}>
      {content}
    </nav>
  );
};
