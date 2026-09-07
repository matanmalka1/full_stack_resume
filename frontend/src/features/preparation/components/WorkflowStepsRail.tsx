import { Fragment } from "react";

import { Check, Circle } from "lucide-react";
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

const railClasses = surfaceClasses(
  "w-full min-w-0 overflow-hidden bg-cv-surface shadow-surface",
);

const stepCardClasses: Record<WorkflowStepState, string> = {
  complete: "text-cv-text",
  current: "text-cv-text",
  upcoming: "text-cv-text-muted",
};

const stepMarkClasses: Record<WorkflowStepState, string> = {
  complete: "border-cv-success/25 bg-cv-success-soft text-cv-success",
  current:
    "border-cv-accent bg-cv-accent text-cv-on-accent shadow-surface ring-4 ring-cv-accent-soft",
  upcoming: "border-cv-border bg-cv-surface text-cv-text-muted",
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
      "relative z-10 flex size-9 shrink-0 items-center justify-center rounded-pill border",
      "text-support font-bold transition-[background-color,border-color,color,box-shadow] duration-200",
      stepMarkClasses[state],
    )}
  >
    {state === "complete" ? (
      <Check className="size-4 stroke-[2.75]" />
    ) : state === "upcoming" ? (
      <span className="flex items-center gap-1">
        <span>{index + 1}</span>
      </span>
    ) : (
      index + 1
    )}
  </span>
);

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
      "relative flex min-w-[9.75rem] flex-1 items-center gap-3 rounded-surface px-3 py-3 text-start",
      "transition-[background-color,box-shadow,border-color] duration-200",
      stepCardClasses[step.state],
      step.state === "current" && "bg-cv-accent-soft/55",
      step.here === true && step.state !== "current" && "bg-cv-surface-muted",
      step.href !== undefined && "group-hover:bg-cv-surface-muted group-hover:shadow-surface",
    )}
  >
    <StepMark index={index} state={step.state} />

    <span className="flex min-w-0 flex-1 flex-col gap-0.5">
      <span
        className={cx(
          "whitespace-nowrap text-support",
          finalCompletion
            ? "font-bold text-cv-success"
            : step.state === "current"
              ? "font-bold text-cv-accent"
              : step.state === "complete"
                ? "font-semibold text-cv-text"
                : "font-medium text-cv-text-muted",
        )}
      >
        {step.label}
      </span>

      <span className="flex min-h-5 items-center gap-1.5 text-[0.75rem] leading-none">
        {step.here === true ? (
          <span className="inline-flex items-center gap-1 font-medium text-cv-accent">
            <Circle aria-hidden="true" className="size-1.5 fill-current" />
            העמוד הפתוח
          </span>
        ) : step.state === "complete" ? (
          <span className="text-cv-text-muted">הושלם</span>
        ) : step.state === "current" ? (
          <span className="font-medium text-cv-accent">בתהליך</span>
        ) : (
          <span className="text-cv-text-muted">בהמשך</span>
        )}
      </span>
    </span>
  </span>
);

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

  const progressText = completed
    ? `הושלם, ${steps.length} מתוך ${steps.length}`
    : position === null
      ? null
      : elsewhere
        ? `העבודה בשלב ${position} מתוך ${steps.length}: ${current?.label}`
        : `שלב ${position} מתוך ${steps.length}`;

  const header = (
    <div aria-hidden="true" className="border-b border-cv-border bg-cv-surface-muted/55 px-4 py-3 sm:px-5">
      <div className="flex min-w-0 flex-wrap items-center justify-between gap-x-6 gap-y-2">
        <div className="min-w-0">
          <div className="flex flex-wrap items-baseline gap-x-2 gap-y-1">
            <span className="text-support font-bold text-cv-text">{label}</span>
            {progressText === null ? null : <span className="text-support text-cv-text-muted">{progressText}</span>}
          </div>

          {hint === undefined ? null : (
            <p className="mt-0.5 truncate text-[0.8125rem] text-cv-text-muted">{hint}</p>
          )}
        </div>

        {here === undefined ? null : (
          <span className="inline-flex shrink-0 items-center gap-1.5 rounded-pill border border-cv-border bg-cv-surface px-2.5 py-1 text-[0.75rem] font-medium text-cv-text-muted shadow-surface">
            <span aria-hidden="true" className="size-1.5 rounded-pill bg-cv-accent" />
            עמוד {here.label}
          </span>
        )}
      </div>
    </div>
  );

  const row = (
    <div className="overflow-x-auto px-3 py-3 sm:px-4">
      <div className="flex min-w-[34rem] items-center">
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
                  aria-current={step.state === "current" ? "step" : undefined}
                  aria-label={
                    finalCompletion
                      ? `פתיחת שלב ${step.label}`
                      : `${step.state === "complete" ? "חזרה" : "מעבר"} לשלב ${step.label}`
                  }
                  className="group min-w-0 flex-1 rounded-surface"
                  to={step.href}
                >
                  {body}
                </Link>
              )}

              {next === undefined ? null : (
                <span className="relative mx-1.5 flex h-9 min-w-8 flex-1 items-center" aria-hidden="true">
                  <span
                    className={cx(
                      "h-0.5 w-full rounded-pill transition-colors duration-200",
                      connectorClasses[next.state],
                    )}
                  />
                </span>
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
        <div aria-hidden="true">
          {header}
          {row}
        </div>
      </div>
    );
  }

  return (
    <nav aria-label={description} className={railClasses}>
      {header}
      {row}
    </nav>
  );
};