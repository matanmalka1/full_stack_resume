import { queryOptions } from "@tanstack/react-query";

import { ApiProblem, apiRequest } from "./client";
import type { Operation } from "./contracts";

/* Which statuses end an Operation is a lifecycle rule the backend owns and now reports,
   so nothing here re-derives it. */
export const isTerminalOperation = (operation: Operation | undefined): boolean =>
  operation?.is_terminal === true;

/* No WebSocket, no SSE. A fixed interval the user can reason about, stopped the moment
   the Operation reaches a terminal status. */
export const OPERATION_POLL_INTERVAL_MS = 1500;

/* 408 and 429 are 4xx that say "later", not "never": they stay retryable. Everything
   else in the 4xx range is the request itself being wrong, and repeating it cannot
   change the answer. A 5xx, a timeout, and a dropped connection are all transient as
   far as this screen can tell, so they keep polling. */
const RETRYABLE_CLIENT_STATUSES = new Set([408, 429]);

export const isPermanentFailure = (error: unknown): boolean => {
  if (!(error instanceof ApiProblem)) {
    return false;
  }

  const { status } = error.problem;
  return status >= 400 && status < 500 && !RETRYABLE_CLIENT_STATUSES.has(status);
};

export const operationQueryOptions = (operationId: string) =>
  queryOptions({
    queryKey: ["operation", operationId],
    queryFn: async ({ signal }) => {
      const response = await apiRequest<Operation>(
        `/api/v1/operations/${operationId}`,
        { signal },
      );
      return response.data;
    },
    /* A transient failure keeps the interval alive, so a momentary backend hiccup does
       not end the poll. A permanent one stops it: an Operation that does not exist will
       not start existing, and retrying that request every 1.5s forever is a request
       loop the user cannot see or stop. */
    refetchInterval: (query) =>
      isTerminalOperation(query.state.data) || isPermanentFailure(query.state.error)
        ? false
        : OPERATION_POLL_INTERVAL_MS,
  });
