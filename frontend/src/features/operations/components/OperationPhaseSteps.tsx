import { Check } from "lucide-react";

import type { OperationPhase } from "@/api/contracts";
import { cx } from "@/ui/cx";
import { operationPhaseStep, operationPhaseSteps } from "../model/operationPhases";

/* Where a live run is, as four named steps. It replaces a bar that swept back and forth:
   Operations report no percentage, so the bar looked like progress while measuring
   nothing, and the phase the record does report went unshown. */
export const OperationPhaseSteps = ({ phase }: { phase: OperationPhase }) => {
  const current = operationPhaseStep(phase);

  return (
    <ol aria-label="שלבי ההרצה" className="flex flex-wrap items-center gap-x-1.5 gap-y-1 text-caption">
      {operationPhaseSteps.map((label, index) => {
        const done = index < current;
        const active = index === current;
        return (
          <li
            aria-current={active ? "step" : undefined}
            className={cx(
              "flex items-center gap-1",
              active ? "font-bold text-cv-accent" : done ? "text-cv-text" : "text-cv-text-muted",
            )}
            key={label}
          >
            {index === 0 ? null : (
              <span aria-hidden="true" className="text-cv-text-muted">
                ›
              </span>
            )}
            {done ? <Check aria-hidden="true" className="size-icon-sm text-cv-success" /> : null}
            {label}
          </li>
        );
      })}
    </ol>
  );
};
