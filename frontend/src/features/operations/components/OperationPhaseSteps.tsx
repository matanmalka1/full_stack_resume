import { Check } from "lucide-react";
import { Fragment } from "react";

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
   never colour alone. */
export const OperationPhaseSteps = ({ phase }: { phase: OperationPhase }) => {
  const current = operationPhaseStep(phase);

  return (
    <ol aria-label="שלבי ההרצה" className="flex flex-wrap items-center gap-x-1.5 gap-y-1.5 text-caption">
      {operationPhaseSteps.map((label, index) => {
        const done = index < current;
        const active = index === current;
        return (
          <Fragment key={label}>
            {index === 0 ? null : (
              <li aria-hidden="true" className="flex items-center">
                <span className={cx("h-px w-3", index <= current ? "bg-cv-accent" : "workflow-track-upcoming")} />
              </li>
            )}
            <li
              aria-current={active ? "step" : undefined}
              className={cx(
                "flex items-center gap-1.5",
                active ? "font-bold text-cv-text" : done ? "font-medium text-cv-text" : "text-cv-text-muted",
              )}
            >
              <span
                aria-hidden="true"
                className={cx(
                  "flex size-4 shrink-0 items-center justify-center rounded-pill border",
                  done
                    ? "border-cv-accent bg-cv-accent text-cv-on-accent"
                    : active
                      ? "border-cv-accent bg-cv-surface"
                      : "border-cv-border-strong bg-cv-surface",
                )}
              >
                {done ? <Check className="size-2.5 [stroke-width:var(--stroke-icon-strong)]" /> : null}
                {active ? <span className="size-1.5 rounded-pill bg-cv-accent motion-safe:animate-pulse" /> : null}
              </span>
              {label}
            </li>
          </Fragment>
        );
      })}
    </ol>
  );
};
