import type { ReactNode } from "react";

import { ErrorCallout } from "../app/ErrorCallout";
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
}: QueryStateProps) => {
  const errorState =
    error !== null && error !== undefined && fallbackTitle !== undefined ? (
      <ErrorCallout
        className={className}
        error={error}
        fallbackDetail={fallbackDetail}
        fallbackTitle={fallbackTitle}
      />
    ) : null;

  if (loading) {
    return (
      errorState ?? <p className={cx("text-body text-cv-text-muted", className)}>{loadingLabel}</p>
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
