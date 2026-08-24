import { CircleCheck } from "lucide-react";

import { cx } from "./cx";

export type WorkflowStepState = "complete" | "current" | "upcoming";

export interface WorkflowStep {
  label: string;
  state: WorkflowStepState;
}

const stateClasses: Record<WorkflowStepState, string> = {
  complete: "text-cv-success",
  current: "rounded-control bg-cv-accent-soft font-semibold text-cv-accent",
  upcoming: "text-cv-text-muted",
};

interface WorkflowStepsProps {
  label: string;
  steps: WorkflowStep[];
}

/* A.1: the landmark shows completed, current, and future stages. Future stages are not
   navigable, so the steps are text, never links. */
export const WorkflowSteps = ({ label, steps }: WorkflowStepsProps) => {
  return (
    <nav aria-label={label} className="border-b border-cv-border bg-cv-surface">
      <ol className="mx-auto flex max-w-7xl gap-2 overflow-x-auto px-6 py-3 text-support">
        {steps.map((step) => (
          <li
            aria-current={step.state === "current" ? "step" : undefined}
            className={cx(
              "flex shrink-0 items-center gap-2 px-3 py-2",
              stateClasses[step.state],
            )}
            key={step.label}
          >
            {step.state === "complete" ? (
              <CircleCheck aria-hidden="true" className="size-4 shrink-0" />
            ) : null}
            {step.label}
          </li>
        ))}
      </ol>
    </nav>
  );
};
