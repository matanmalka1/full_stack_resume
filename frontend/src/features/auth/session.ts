import type { QueryClient } from "@tanstack/react-query";

/* What a signed-in reader leaves in this browser: saved board views, the intake draft,
   unsent editor text, the board's return address, the sidebar and theme choices. Signing
   out removes all of it, so the next person at the keyboard starts from nothing.

   A session that merely expires keeps it: the reader signs back in and finds their
   unsent work where they left it. */
export const clearSignedInBrowserState = (queryClient: QueryClient): void => {
  queryClient.clear();
  for (const storage of [globalThis.localStorage, globalThis.sessionStorage]) {
    try {
      storage.clear();
    } catch {
      // Storage disabled or unavailable: nothing was kept there to clear.
    }
  }
};

/* A `next` worth returning to: a path inside this app, never another origin. */
export const safeNextPath = (next: string | null): string =>
  next !== null && next.startsWith("/") && !next.startsWith("//") && !next.startsWith("/login") ? next : "/";
