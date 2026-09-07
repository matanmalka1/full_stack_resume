import { Callout } from "./Callout";

interface ErrorCalloutProps {
  className?: string;
  error: unknown;
  fallbackDetail?: string;
  fallbackTitle: string;
}

const defaultFallbackDetail = "הפנייה לשרת נכשלה. אפשר לרענן את העמוד ולנסות שוב.";
export const briefServerFailureDetail = "הפנייה לשרת נכשלה.";

const problemDetailsFrom = (error: unknown): { detail: string; title: string } | null => {
  if (typeof error !== "object" || error === null || !("problem" in error)) {
    return null;
  }

  const problem = error.problem;
  if (typeof problem !== "object" || problem === null || !("title" in problem) || !("detail" in problem)) {
    return null;
  }

  return typeof problem.title === "string" && typeof problem.detail === "string"
    ? { detail: problem.detail, title: problem.title }
    : null;
};

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
  fallbackDetail = defaultFallbackDetail,
  fallbackTitle,
}: ErrorCalloutProps) => {
  const problem = problemDetailsFrom(error);

  return (
    <Callout className={className} role="alert" title={problem?.title ?? fallbackTitle} tone="blocker">
      {problem?.detail ?? fallbackDetail}
    </Callout>
  );
};
