import { useEffect, useRef } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import type { AutoDraftSources } from "./autoDraft";

export interface PreparationContinuation {
  applicationId: string;
  decisionSources?: AutoDraftSources;
  draftOperationId?: string;
}

/* This is navigation intent in this tab's history entry, never workflow authority.
   BrowserRouter retains entry state on refresh; copying a URL confers no intent.
   Canonical sources, availability and activation must still be verified by the API. */
export const usePreparationContinuation = (applicationId: string) => {
  const location = useLocation();
  const navigate = useNavigate();
  const scope = useRef({ applicationId, location, mounted: true });
  useEffect(() => {
    scope.current = { applicationId, location, mounted: true };
    return () => {
      scope.current.mounted = false;
    };
  }, [applicationId, location]);
  const state = location.state as Record<string, unknown> | null;
  const candidate = state?.preparationContinuation as PreparationContinuation | undefined;
  const intent = candidate?.applicationId === applicationId ? candidate : undefined;
  const mark = (continuation: PreparationContinuation): boolean => {
    const current = scope.current;
    if (!current.mounted || current.applicationId !== continuation.applicationId) return false;
    const previous = current.location.state as Record<string, unknown> | null;
    const nextState = { ...previous, preparationContinuation: continuation };
    // Keep consecutive marks in the same event from losing another state field.
    current.location = { ...current.location, state: nextState };
    navigate(
      { pathname: current.location.pathname, search: current.location.search, hash: current.location.hash },
      { replace: true, state: nextState },
    );
    return true;
  };
  return { intent, mark };
};
