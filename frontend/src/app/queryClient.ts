import { QueryClient } from "@tanstack/react-query";

import { isPermanentFailure } from "@/api/client";

/* A read is retried once, and only when a second attempt could answer differently: a
   missing record or a refused request is shown at once instead of after a retry that
   was bound to get the same 4xx. */
export const MAX_QUERY_RETRIES = 1;

export const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: (failureCount, error) => failureCount < MAX_QUERY_RETRIES && !isPermanentFailure(error),
    },
    mutations: {
      retry: false,
    },
  },
});
