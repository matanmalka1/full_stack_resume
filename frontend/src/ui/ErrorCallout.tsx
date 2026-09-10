import type { ProblemDetails } from "@/api/client";
import { Callout } from "./Callout";
import { localizedProblem, problemFieldIssues } from "./errorMessages";

interface ErrorCalloutProps {
  className?: string;
  error: unknown;
  fallbackDetail?: string;
  fallbackTitle: string;
}

const defaultFallbackDetail = "הפנייה לשרת נכשלה. אפשר לרענן את העמוד ולנסות שוב.";
export const briefServerFailureDetail = "הפנייה לשרת נכשלה.";

const problemDetailsFrom = (error: unknown): ProblemDetails | null => {
  if (typeof error !== "object" || error === null || !("problem" in error)) {
    return null;
  }

  const problem = error.problem;
  if (
    typeof problem !== "object" ||
    problem === null ||
    !("title" in problem) ||
    !("detail" in problem) ||
    !("code" in problem) ||
    !("type" in problem) ||
    !("status" in problem)
  ) {
    return null;
  }

  return typeof problem.title === "string" &&
    typeof problem.detail === "string" &&
    typeof problem.code === "string" &&
    typeof problem.type === "string" &&
    typeof problem.status === "number"
    ? (problem as ProblemDetails)
    : null;
};

/** One presentation boundary for failed API queries and mutations.
 *
 * Stable API codes select user-facing Hebrew copy. The server's safe detail is
 * retained only as forward-compatible copy for a code this client does not yet
 * know. Local programming errors get only the contextual fallback supplied by
 * the owning screen; their exception text is never rendered into the page.
 *
 * The code itself is not shown. Structured request issues are rendered as field
 * errors instead of discarding the actionable part of a 422 response.
 */
export const ErrorCallout = ({
  className,
  error,
  fallbackDetail = defaultFallbackDetail,
  fallbackTitle,
}: ErrorCalloutProps) => {
  const problem = problemDetailsFrom(error);
  const presentation = problem === null ? null : localizedProblem(problem);
  const fieldIssues = problem === null ? [] : problemFieldIssues(problem);

  return (
    <Callout className={className} role="alert" title={presentation?.title ?? fallbackTitle} tone="blocker">
      <p dir={presentation?.known === false ? "auto" : undefined}>{presentation?.detail ?? fallbackDetail}</p>
      {fieldIssues.length === 0 ? null : (
        <ul className="mt-2 list-disc space-y-1 ps-5">
          {fieldIssues.map((issue) => (
            <li key={issue}>{issue}</li>
          ))}
        </ul>
      )}
    </Callout>
  );
};
