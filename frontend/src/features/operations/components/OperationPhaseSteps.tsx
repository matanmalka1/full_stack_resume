import { Check, X } from "lucide-react";
import { Fragment, type ReactNode } from "react";

import type { OperationPhase } from "@/api/contracts";
import { cx } from "@/ui/cx";
import { PENDING_STEP, operationPhaseStep, operationPhaseSteps } from "../model/operationPhases";

/* How the steps are laid out for their host:
   - "row": marks and words on one line joined by rules - the corner panel and the
     failure report, where the steps are one line among others;
   - "stacked": one step per line down a card, joined by a vertical rule - a phone's run
     screen, where the steps are the run's body;
   - "columns": four equal columns, each mark over its word - a wide run screen. */
type StepsLayout = "row" | "stacked" | "columns";

type StepState = "done" | "active" | "failed" | "upcoming";

const markClasses: Record<StepState, string> = {
  done: "bg-cv-accent text-cv-on-accent",
  failed: "bg-cv-accent text-cv-on-accent",
  active: "border-2 border-cv-accent bg-cv-surface",
  upcoming: "border-[1.5px] border-cv-border-strong bg-cv-surface",
};

const Mark = ({ size, state }: { size: "sm" | "md"; state: StepState }) => (
  <span
    aria-hidden="true"
    className={cx(
      "flex shrink-0 items-center justify-center rounded-pill",
      size === "sm" ? "size-5.5" : "size-6.5",
      markClasses[state],
    )}
  >
    {state === "done" ? (
      <Check className={cx(size === "sm" ? "size-2.5" : "size-3.5", "[stroke-width:var(--stroke-icon-strong)]")} />
    ) : null}
    {state === "failed" ? (
      <X className={cx(size === "sm" ? "size-2.5" : "size-3.5", "[stroke-width:var(--stroke-icon-strong)]")} />
    ) : null}
    {state === "active" ? (
      <span
        className={cx("rounded-pill bg-cv-accent motion-safe:animate-pulse", size === "sm" ? "size-1.5" : "size-2.5")}
      />
    ) : null}
  </span>
);

/* Where a live run is, as named steps. Operations report no percentage, so the run is
   shown as the stretch it is in rather than as a bar measuring nothing.

   Shape and weight carry each step's state, never colour alone: a filled mark with a tick
   for a step behind the run, a ring with a breathing dot for the one it is in, an outline
   for what is ahead, and a filled mark with a cross - and the word - for the step a run
   that ended without a result stopped on.

   `pending` is a run asked for before its record exists: it is on the first step.
   `from` leaves out the steps before it - a failure report starts at the queue, since
   sending is not where anything went wrong. `activeNote` is a line under the open step's
   name - how long it has run. */
export const OperationPhaseSteps = ({
  activeNote,
  failedStep,
  from = 0,
  layout = "row",
  pending = false,
  phase,
}: {
  activeNote?: ReactNode;
  failedStep?: number | undefined;
  from?: number;
  layout?: StepsLayout;
  pending?: boolean;
  phase: OperationPhase;
}) => {
  const current = failedStep ?? (pending ? PENDING_STEP : operationPhaseStep(phase));
  const stateOf = (index: number): StepState =>
    failedStep === index ? "failed" : index < current ? "done" : index === current ? "active" : "upcoming";
  const steps = operationPhaseSteps.map((label, index) => ({ index, label, state: stateOf(index) })).slice(from);

  const word = (label: string, state: StepState) => (
    <>
      {label}
      {state === "failed" ? " · נכשל" : null}
    </>
  );
  const weight = (state: StepState) =>
    state === "active" || state === "failed" ? "font-bold text-cv-text" : "text-cv-text-muted";

  if (layout === "columns") {
    return (
      <ol aria-label="שלבי ההרצה" className="grid grid-cols-4 gap-3 text-label">
        {steps.map(({ label, state }) => (
          <li
            aria-current={state === "active" || state === "failed" ? "step" : undefined}
            className={cx("flex flex-col items-center gap-2 text-center", weight(state))}
            key={label}
          >
            <Mark size="md" state={state} />
            <span>{word(label, state)}</span>
            {state === "active" && activeNote !== undefined ? (
              <span className="-mt-1 text-caption font-medium text-cv-text-muted">{activeNote}</span>
            ) : null}
          </li>
        ))}
      </ol>
    );
  }

  if (layout === "stacked") {
    return (
      <ol aria-label="שלבי ההרצה" className="flex flex-col text-body">
        {steps.map(({ label, state }, position) => (
          <li
            aria-current={state === "active" || state === "failed" ? "step" : undefined}
            className={cx("relative flex items-start gap-3", weight(state))}
            key={label}
          >
            <span className="flex flex-col items-center self-stretch">
              <Mark size="sm" state={state} />
              {position === steps.length - 1 ? null : (
                <span
                  aria-hidden="true"
                  className={cx("min-h-3 w-0.5 flex-1", state === "upcoming" ? "bg-cv-border" : "bg-cv-accent")}
                />
              )}
            </span>
            <span className={cx("flex min-w-0 flex-col", position === steps.length - 1 ? "pb-0" : "pb-4")}>
              <span className="leading-6">{word(label, state)}</span>
              {state === "active" && activeNote !== undefined ? (
                <span className="text-support font-normal text-cv-text-muted">{activeNote}</span>
              ) : null}
            </span>
          </li>
        ))}
      </ol>
    );
  }

  return (
    <ol aria-label="שלבי ההרצה" className="flex flex-wrap items-center gap-x-2 gap-y-1.5 text-label">
      {steps.map(({ label, state }, position) => (
        <Fragment key={label}>
          {position === 0 ? null : <li aria-hidden="true" className="h-px min-w-3 flex-1 bg-cv-border-soft" />}
          <li
            aria-current={state === "active" || state === "failed" ? "step" : undefined}
            className={cx("flex items-center gap-1.5", weight(state))}
          >
            <Mark size="sm" state={state} />
            <span className="flex min-w-0 flex-col">
              <span>{word(label, state)}</span>
              {state === "active" && activeNote !== undefined ? (
                <span className="text-support font-normal text-cv-text-muted">{activeNote}</span>
              ) : null}
            </span>
          </li>
        </Fragment>
      ))}
    </ol>
  );
};
