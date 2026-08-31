import { ApiProblem } from "../api/client";
import { Callout } from "../ui/Callout";

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
 *
 * The failure code is not shown. `problem.detail` is the server's own sentence about
 * what went wrong, and it is already the body of this callout; the code beside it named
 * the same failure in a vocabulary the reader has no use for.
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
    </Callout>
  );
};
