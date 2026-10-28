import { Check, X } from "lucide-react";
import { Fragment, type ReactNode } from "react";

import type { OperationPhase } from "@/api/contracts";
import { cx } from "@/ui/cx";
import { operationPhaseStep, operationPhaseSteps } from "../model/operationPhases";

/* Where a live run is, as named steps. It replaces a bar that swept back and forth:
   Operations report no percentage, so the bar looked like progress while measuring
   nothing, and the phase the record does report went unshown.

   Drawn the way the workflow spine draws its steps, at a smaller size: a filled mark with
   a tick for a phase behind the run, a ring with a breathing dot for the one it is in, a
   plain outline for what is ahead, joined by a line that is solid as far as the run has
   come. The steps were once words between `›` marks, which read as a breadcrumb trail -
   somewhere to navigate - rather than as a run moving. Shape and weight carry the state,
   never colour alone.

   `stackOnPhone`: below the large breakpoint the steps run down the card, a label on the
   reading side and its mark on the far one, joined by a vertical line - for a host where
   the steps are the run's body rather than one line of a report.

   `prominent`: from the large breakpoint each step stands as a column - a larger mark over
   its name - and the line between two marks stretches to share the row, for the wide
   screen's centred run card, where the steps are the card's middle rather than a line of
   a report.

   `activeNote` is a line under the open step's name - how long it has run. `failedStep`
   marks the step a run that ended without a result stopped on: a filled mark with a
   cross and the word, so where it broke is a shape and a word as well as a position. */
export const OperationPhaseSteps = ({
  activeNote,
  failedStep,
  phase,
  prominent = false,
  stackOnPhone = false,
}: {
  activeNote?: ReactNode;
  failedStep?: number | undefined;
  phase: OperationPhase;
  prominent?: boolean;
  stackOnPhone?: boolean;
}) => {
  const current = failedStep ?? operationPhaseStep(phase);

  return (
    <ol
      aria-label="שלבי ההרצה"
      className={cx(
        "flex flex-wrap items-center gap-x-1.5 gap-y-1.5 text-caption",
        stackOnPhone && "max-lg:flex-col max-lg:flex-nowrap max-lg:items-stretch max-lg:gap-0 max-lg:text-body",
        prominent && "lg:flex-nowrap lg:items-start lg:gap-3 lg:text-support",
      )}
    >
      {operationPhaseSteps.map((label, index) => {
        const done = index < current;
        const failed = failedStep === index;
        const active = index === current && !failed;
        return (
          <Fragment key={label}>
            {index === 0 ? null : (
              <li
                aria-hidden="true"
                className={cx(
                  "flex items-center",
                  stackOnPhone && "max-lg:me-[0.6875rem] max-lg:self-end",
                  prominent && "lg:mt-3.5 lg:min-w-6 lg:flex-1",
                )}
              >
                <span
                  className={cx(
                    "h-px w-3",
                    stackOnPhone && "max-lg:h-4 max-lg:w-px",
                    prominent && "lg:w-full",
                    index <= current ? "bg-cv-accent" : "workflow-track-upcoming",
                  )}
                />
              </li>
            )}
            <li
              aria-current={active || failed ? "step" : undefined}
              className={cx(
                "flex items-center gap-1.5",
                stackOnPhone && "max-lg:flex-row-reverse max-lg:justify-between max-lg:gap-3",
                prominent && "lg:shrink-0 lg:flex-col lg:gap-2 lg:text-center",
                active || failed ? "font-bold text-cv-text" : done ? "font-medium text-cv-text" : "text-cv-text-muted",
              )}
            >
              <span
                aria-hidden="true"
                className={cx(
                  "flex size-4 shrink-0 items-center justify-center rounded-pill border",
                  stackOnPhone && "max-lg:size-6 max-lg:border-2",
                  prominent && "lg:size-7 lg:border-2",
                  done || failed
                    ? "border-cv-accent bg-cv-accent text-cv-on-accent"
                    : active
                      ? "border-cv-accent bg-cv-surface"
                      : "border-cv-border-strong bg-cv-surface",
                )}
              >
                {done ? (
                  <Check
                    className={cx(
                      "size-2.5 [stroke-width:var(--stroke-icon-strong)]",
                      stackOnPhone && "max-lg:size-3.5",
                      prominent && "lg:size-4",
                    )}
                  />
                ) : null}
                {failed ? (
                  <X
                    className={cx(
                      "size-2.5 [stroke-width:var(--stroke-icon-strong)]",
                      stackOnPhone && "max-lg:size-3.5",
                      prominent && "lg:size-4",
                    )}
                  />
                ) : null}
                {active ? (
                  <span
                    className={cx(
                      "size-1.5 rounded-pill bg-cv-accent motion-safe:animate-pulse",
                      stackOnPhone && "max-lg:size-2.5",
                      prominent && "lg:size-3",
                    )}
                  />
                ) : null}
              </span>
              <span className={cx("flex min-w-0 flex-col", prominent && "lg:items-center")}>
                <span>
                  {label}
                  {failed ? " · נכשל" : null}
                </span>
                {active && activeNote !== undefined ? (
                  <span className="text-support font-normal text-cv-text-muted">{activeNote}</span>
                ) : null}
              </span>
            </li>
          </Fragment>
        );
      })}
    </ol>
  );
};
