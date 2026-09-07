import { QueryClientProvider } from "@tanstack/react-query";
import { RouterProvider } from "react-router-dom";

import { queryClient } from "./queryClient";
import { router } from "./router";

/* The composition root, and every provider the application has.

   Two, because two is what it needs: the query cache each screen reads server state
   through, and the router. The cache is created once at module scope rather than here,
   so a re-render never replaces it, and it wraps the router because the route elements
   are what query it. */
export const AppProviders = () => {
  return (
    <QueryClientProvider client={queryClient}>
      <RouterProvider router={router} />
    </QueryClientProvider>
  );
};
