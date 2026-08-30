import { ApiProblem } from "../api/client";
import { Callout } from "../ui/Callout";
import { LtrText } from "../ui/LtrText";
import { TechnicalDetails } from "../ui/TechnicalDetails";

interface ErrorCalloutProps {
  className?: string;
  error: unknown;
  fallbackDetail: string;
  fallbackTitle: string;
}

/** One presentation boundary for failed API queries and mutations.
 *
 * API Problem Details remain authoritative when available. Local programming
 * errors get only the safe, contextual fallback supplied by the owning screen;
 * their exception text is never rendered into the page.
 */
export const ErrorCallout = ({
  className,
  error,
  fallbackDetail,
  fallbackTitle,
}: ErrorCalloutProps) => {
  const problem = error instanceof ApiProblem ? error.problem : null;

  return (
    <Callout
      className={className}
      role="alert"
      title={problem?.title ?? fallbackTitle}
      tone="blocker"
    >
      {problem?.detail ?? fallbackDetail}
      {problem === null ? null : (
        <TechnicalDetails className="mt-3">
          <LtrText>
            {problem.code}
            {problem.status > 0 ? ` · HTTP ${problem.status}` : ""}
          </LtrText>
        </TechnicalDetails>
      )}
    </Callout>
  );
};
