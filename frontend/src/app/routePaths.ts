/* Every URL the application builds, in one place. A screen names a destination by calling
   one of these rather than by assembling a path, so a route that moves in `router.tsx`
   moves for every caller at once.
   
   Ids are encoded as a single path segment: an id carrying a slash or a space stays one
   segment instead of splitting into two the router cannot match. */
const segment = (value: string): string => encodeURIComponent(value);

const application = (applicationId: string): string => `/applications/${segment(applicationId)}`;

export const routePaths = {
  home: "/",
  newApplication: "/applications/new",
  settings: "/settings",
  application,
  /* The Application hub with its preparation tab already selected. A second URL for the
     same screen, kept because links and bookmarks name the preparation work directly. */
  preparation: (applicationId: string): string => `${application(applicationId)}/preparation`,
  draft: (applicationId: string): string => `${application(applicationId)}/draft`,
  revision: (revisionId: string): string => `/revisions/${segment(revisionId)}`,
} as const;
