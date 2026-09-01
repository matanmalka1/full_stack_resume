import { queryOptions } from "@tanstack/react-query";

import { ApiProblem, type ApiPath, type ApiResponse, apiRequest } from "./client";
import type { Operation } from "./contracts";

/* Which statuses end an Operation is a lifecycle rule the backend owns and now reports,
   so nothing here re-derives it. */
export const isTerminalOperation = (operation: Operation | undefined): boolean =>
  operation?.is_terminal === true;

/* No WebSocket, no SSE. A fixed interval the user can reason about, stopped the moment
   the Operation reaches a terminal status. */
export const OPERATION_POLL_INTERVAL_MS = 1500;

export const operationQueryKey = (operationId: string) => ["operation", operationId] as const;

const operationPath = (operationId: string): ApiPath =>
  `/api/v1/operations/${encodeURIComponent(operationId)}`;

/* 408 and 429 are 4xx that say "later", not "never": they stay retryable. Everything
   else in the 4xx range is the request itself being wrong, and repeating it cannot
   change the answer. A 5xx, a timeout, and a dropped connection are all transient as
   far as this screen can tell, so they keep polling. */
const RETRYABLE_CLIENT_STATUSES = new Set([408, 429]);

const isPermanentFailure = (error: unknown): boolean => {
  if (!(error instanceof ApiProblem)) {
    return false;
  }

  const { status } = error.problem;
  return status >= 400 && status < 500 && !RETRYABLE_CLIENT_STATUSES.has(status);
};

export const operationQueryOptions = (operationId: string) =>
  queryOptions({
    queryKey: operationQueryKey(operationId),
    /* The poll is its own retry: a transient failure is queried again after 1.5 seconds.
       Inheriting the global immediate retry would only double the request cost of a
       permanently missing Operation before the interval below stops. */
    retry: false,
    queryFn: async ({ signal }) => {
      const response = await apiRequest<Operation>(
        operationPath(operationId),
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

export const cancelOperation = async (operationId: string): Promise<Operation> => {
  const response = await apiRequest<Operation>(
    `${operationPath(operationId)}/cancel`,
    { method: "POST" },
  );
  return response.data;
};

export interface QueuedOperation {
  operation: Operation;
}

/* Every command that queues durable work answers `202` and a `Location` naming the
   Operation it queued (§13). A response without that pair is not a queued Operation this
   client may follow, so it is refused here rather than navigated to. One copy of the
   check: every caller carries the same obligation, and a second copy is the one that
   goes stale. */
export const queuedOperation = (response: ApiResponse<Operation>): QueuedOperation => {
  const expectedLocation = operationPath(response.data.id);

  if (response.status !== 202 || response.location !== expectedLocation) {
    throw new Error("Accepted response did not identify its queued Operation");
  }

  /* The queued Operation itself, and no route to it: it is reported by the screen that
     queued it rather than followed. The `202`/`Location` check above stays - it is the
     §13 contract, not a navigation concern. */
  return { operation: response.data };
};

export const retryOperation = async (
  operationId: string,
  idempotencyKey: string,
): Promise<QueuedOperation> =>
  queuedOperation(
    await apiRequest<Operation>(`${operationPath(operationId)}/retry`, {
      method: "POST",
      idempotencyKey,
    }),
  );
