import type { ReactNode } from "react";

import { NotFoundPage } from "@/app/layout/NotFoundPage";
import { ApiProblem } from "@/api/client";
import { ErrorCallout } from "./ErrorCallout";
import { LiveRegion } from "./LiveRegion";
import { cx } from "./cx";

interface QueryStateProps {
  children?: ReactNode;
  className?: string;
  empty?: boolean;
  emptyState?: ReactNode;
  error?: unknown;
  fallbackDetail?: string;
  fallbackTitle?: string;
  loading?: boolean;
  loadingLabel?: ReactNode;
  loadingState?: ReactNode;
}

/* Query-backed regions always resolve in the same order and place: a failure replaces
   an initial loading message, while a failed refresh can still leave its existing content
   visible. Empty and loaded results share the same body rhythm. The owning screen supplies
   its existing contextual Hebrew copy. */
export const QueryState = ({
  children,
  className,
  empty = false,
  emptyState,
  error,
  fallbackDetail,
  fallbackTitle,
  loading = false,
  loadingLabel,
  loadingState,
}: QueryStateProps) => {
  if (error instanceof ApiProblem && error.problem.status === 404) {
    return <NotFoundPage />;
  }

  const errorState =
    error !== null && error !== undefined && fallbackTitle !== undefined ? (
      <ErrorCallout className={className} error={error} fallbackDetail={fallbackDetail} fallbackTitle={fallbackTitle} />
    ) : null;

  /* The word is announced as well as printed. A region that hands its own `loadingState`
     over already says so - the board's skeleton is a `role="status"` output, the draft and
     revision skeletons open with a `LiveRegion` - while the plain sentence this falls back
     to was a bare paragraph, so the four screens that take the fallback said nothing to a
     reader who cannot see it. Visible and announced are the same node here, which is what
     keeps the two from drifting apart. */
  if (loading) {
    return (
      errorState ??
      loadingState ?? (
        <LiveRegion className={cx("text-body text-cv-text-muted", className)} visuallyHidden={false}>
          {loadingLabel}
        </LiveRegion>
      )
    );
  }

  const content = empty ? emptyState : children;

  if (errorState === null && content === undefined) {
    return null;
  }

  return (
    <div className="flex flex-col gap-6">
      {errorState}
      {content}
    </div>
  );
};
