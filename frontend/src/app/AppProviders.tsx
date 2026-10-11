import { QueryClientProvider } from "@tanstack/react-query";
import { RouterProvider } from "react-router-dom";

import { onSessionLost } from "@/api/client";
import { routePaths } from "@/navigation/routePaths";
import { queryClient } from "./queryClient";
import { router } from "./router";

/* A session that ends under an open screen - expired, revoked, or signed out on another
   device - drops everything read under it and returns to sign-in, which brings the reader
   back here afterwards. Unsent work in browser storage is kept for that return. */
onSessionLost(() => {
  const { pathname, search, hash } = router.state.location;
  if (pathname === "/login") return;
  queryClient.clear();
  void router.navigate(routePaths.login(`${pathname}${search}${hash}`), { replace: true });
});

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
