import { Check } from "lucide-react";

import { cx } from "./cx";

export type WorkflowStepState = "complete" | "current" | "upcoming";

export interface WorkflowStep {
  label: string;
  state: WorkflowStepState;
}

const stateClasses: Record<WorkflowStepState, string> = {
  complete: "text-cv-text-muted",
  current: "font-bold text-cv-accent",
  upcoming: "text-cv-text-muted/70",
};

const nodeClasses: Record<WorkflowStepState, string> = {
  complete: "border-cv-success bg-cv-success text-cv-on-accent",
  current: "border-cv-accent bg-cv-accent text-cv-on-accent ring-3 ring-cv-accent-soft",
  upcoming: "border-cv-border-strong/40 bg-cv-surface text-cv-text-muted",
};

interface WorkflowStepsProps {
  label: string;
  steps: WorkflowStep[];
}

/* A.1: the landmark shows completed, current, and future stages. Future stages are not
   navigable, so the steps are text, never links.

   It is a breadcrumb on the header line rather than a band of its own: the stage is
   orientation, and at nine rem of full-width chrome it was pushing the actual work of
   every screen below the fold. Narrow widths keep only the current step, which is the
   "current-step summary" A.4 frame 4 asks for. */
export const WorkflowSteps = ({ label, steps }: WorkflowStepsProps) => {
  const current = steps.find((step) => step.state === "current");

  return (
    <nav aria-label={label} className="min-w-0">
      <ol className="flex items-center gap-1 md:gap-1.5">
        {steps.map((step, index) => (
          <li
            aria-current={step.state === "current" ? "step" : undefined}
            className={cx(
              "items-center gap-1.5 text-support",
              /* Below md only the current step is shown, so the breadcrumb never
                 wraps the header onto a second line. */
              step.state === "current" ? "flex" : "hidden md:flex",
              stateClasses[step.state],
            )}
            key={step.label}
          >
            <span
              className={cx(
                "flex size-5 shrink-0 items-center justify-center rounded-pill border text-[0.6875rem] font-bold",
                nodeClasses[step.state],
              )}
            >
              {step.state === "complete" ? (
                <Check aria-hidden="true" className="size-3" strokeWidth={3} />
              ) : (
                <span aria-hidden="true">{index + 1}</span>
              )}
            </span>
            <span className="whitespace-nowrap">{step.label}</span>
            {index === steps.length - 1 ? null : (
              <span
                aria-hidden="true"
                className={cx(
                  "ms-1 hidden h-px w-4 md:block lg:w-6",
                  step.state === "complete" ? "bg-cv-success/50" : "bg-cv-border",
                )}
              />
            )}
          </li>
        ))}
      </ol>
      {/* The compact form drops the other steps visually, so the position is still
          stated in text for anyone reading only the current one. */}
      {current === undefined ? null : (
        <span className="sr-only md:hidden">
          {`שלב ${steps.indexOf(current) + 1} מתוך ${steps.length}`}
        </span>
      )}
    </nav>
  );
};
