import { Check } from "lucide-react";

import { cx } from "./cx";

export type WorkflowStepState = "complete" | "current" | "upcoming";

export interface WorkflowStep {
  label: string;
  state: WorkflowStepState;
}

const stateClasses: Record<WorkflowStepState, string> = {
  complete: "text-cv-success",
  current: "font-semibold text-cv-accent",
  upcoming: "text-cv-text-muted",
};

const nodeClasses: Record<WorkflowStepState, string> = {
  complete: "border-cv-success bg-cv-success text-cv-on-accent",
  current: "border-cv-accent bg-cv-accent text-cv-on-accent ring-4 ring-cv-accent-soft",
  upcoming: "border-cv-border-strong bg-cv-surface text-cv-text-muted",
};

interface WorkflowStepsProps {
  label: string;
  steps: WorkflowStep[];
}

/* A.1: the landmark shows completed, current, and future stages. Future stages are not
   navigable, so the steps are text, never links. */
export const WorkflowSteps = ({ label, steps }: WorkflowStepsProps) => {
  return (
    <nav
      aria-label={label}
      className="overflow-x-auto border-b border-cv-border bg-cv-surface/80"
    >
      <ol className="mx-auto flex min-w-[42rem] max-w-5xl px-6 py-4 text-support">
        {steps.map((step, index) => (
          <li
            aria-current={step.state === "current" ? "step" : undefined}
            className={cx(
              "relative flex flex-1 flex-col items-center gap-2 px-2 text-center",
              stateClasses[step.state],
            )}
            key={step.label}
          >
            {index === steps.length - 1 ? null : (
              <span
                aria-hidden="true"
                className={cx(
                  "absolute top-[1.125rem] start-[calc(50%+1.25rem)] h-0.5 w-[calc(100%-2.5rem)]",
                  step.state === "complete" ? "bg-cv-success" : "bg-cv-border",
                )}
              />
            )}
            <span
              className={cx(
                "relative z-10 flex size-9 items-center justify-center rounded-pill border text-support font-bold shadow-surface transition-transform duration-200",
                nodeClasses[step.state],
              )}
            >
              {step.state === "complete" ? (
                <Check aria-hidden="true" className="size-4" strokeWidth={3} />
              ) : (
                <span aria-hidden="true">{index + 1}</span>
              )}
            </span>
            <span>{step.label}</span>
          </li>
        ))}
      </ol>
    </nav>
  );
};
