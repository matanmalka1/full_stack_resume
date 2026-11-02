import { Fragment } from "react";

import { Check } from "lucide-react";
import { Link } from "react-router-dom";

import { ProgressSegments } from "@/ui/ProgressSegments";
import { cx } from "@/ui/cx";

type WorkflowStepState = "complete" | "current" | "upcoming";

export interface WorkflowStep {
  here?: boolean;
  href?: string;
  label: string;
  state: WorkflowStepState;
}

interface WorkflowStepsRailProps {
  label: string;
  steps: WorkflowStep[];
}

const stepMarkClasses: Record<WorkflowStepState, string> = {
  complete: "bg-cv-accent text-cv-on-accent",
  current: "bg-cv-accent text-cv-on-accent",
  upcoming: "border-[1.5px] border-cv-border-strong text-cv-text-muted",
};

const stepLabelClasses: Record<WorkflowStepState, string> = {
  complete: "text-cv-text-muted",
  current: "font-extrabold text-cv-text",
  upcoming: "text-cv-text-muted",
};

/* One step: a mark and its label. The mark carries the state in its shape - a tick for a
   step behind the work, a filled number for the open one, an outlined number ahead - and
   the label in its weight, so colour is never the only signal (A.2). */
const StepBody = ({ index, step }: { index: number; step: WorkflowStep }) => (
  <span className={cx("flex items-center gap-2 text-label whitespace-nowrap", stepLabelClasses[step.state])}>
    <span
      aria-hidden="true"
      className={cx(
        "flex size-6 shrink-0 items-center justify-center rounded-pill text-caption font-bold",
        stepMarkClasses[step.state],
      )}
    >
      {step.state === "complete" ? <Check className="size-3.25 [stroke-width:var(--stroke-icon-strong)]" /> : index + 1}
    </span>
    {step.label}
  </span>
);

/* The workflow's route-level axis, drawn the two ways the design draws it.

   From the large breakpoint it is one row of marks in a card under the step's heading,
   joined by connectors that are solid as far as the work has come. On a phone it is the
   compact band under the header: the open stage's name and its position over one segment
   per stage, filled up to the open one. The phone band is decorative - the nav's own name
   states the position in words, and each reachable step keeps its link in the row. */
export const WorkflowStepsRail = ({ label, steps }: WorkflowStepsRailProps) => {
  const current = steps.find((step) => step.state === "current");
  const position = current === undefined ? null : steps.indexOf(current) + 1;
  const completed = current === undefined && steps.length > 0 && steps.every((step) => step.state === "complete");
  const here = steps.find((step) => step.here === true);
  const hereIndex = steps.findIndex((step) => step.here === true);
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
  const filled = completed ? steps.length : (position ?? 0);

  const content = (
    <>
      {/* The phone's band. The count is led by the stage's name rather than starting the
          line with a digit, which an RTL paragraph can transpose. */}
      <div aria-hidden="true" className="flex flex-col gap-2 lg:hidden">
        <div className="flex items-baseline justify-between gap-3 text-support">
          <span className="font-bold text-cv-text">{completed ? steps.at(-1)?.label : current?.label}</span>
          <span className="text-cv-text-muted">{`${filled} מתוך ${steps.length}`}</span>
        </div>
        <ProgressSegments done={filled} total={steps.length} />
      </div>

      <ol className="flex items-center gap-2.5 max-lg:hidden">
        {steps.map((step, index) => {
          const next = steps[index + 1];
          return (
            <Fragment key={step.label}>
              <li aria-current={step.state === "current" ? "step" : undefined} className="flex shrink-0">
                {step.href === undefined ? (
                  <StepBody index={index} step={step} />
                ) : (
                  <Link
                    aria-label={
                      completed && index === steps.length - 1
                        ? `פתיחת שלב ${step.label}`
                        : `${hereIndex !== -1 && index < hereIndex ? "חזרה" : "מעבר"} לשלב ${step.label}`
                    }
                    className="-m-1.5 flex min-h-11 items-center rounded-item p-1.5 transition-colors hover:bg-cv-surface-muted"
                    to={step.href}
                  >
                    <StepBody index={index} step={step} />
                  </Link>
                )}
              </li>
              {next === undefined ? null : (
                <li
                  aria-hidden="true"
                  className={cx("h-0.5 min-w-3 flex-1", next.state === "upcoming" ? "bg-cv-border" : "bg-cv-accent")}
                />
              )}
            </Fragment>
          );
        })}
      </ol>
    </>
  );

  const frame = "lg:rounded-surface lg:border lg:border-cv-hairline lg:bg-cv-surface lg:px-4.5 lg:py-3.5";

  if (!navigable) {
    return (
      // The rail's real elements are hidden; role="img" presents the composite as one
      // image for assistive tech, which `<img>` (a void element) cannot do.
      // oxlint-disable-next-line jsx-a11y/prefer-tag-over-role
      <div aria-label={description} className={frame} role="img">
        <div aria-hidden="true">{content}</div>
      </div>
    );
  }

  return (
    <nav aria-label={description} className={frame}>
      {content}
    </nav>
  );
};
