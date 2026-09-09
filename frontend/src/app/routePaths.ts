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
  /* One address for the screen that prepares one Application's CV. It once carried a
     second name, `preparation`, resolving to `/applications/:id/preparation` - the same
     screen under a second URL. Two names is what this file exists to prevent: the pair
     drifted, and the two components that locate the reader by comparing against
     `pathname` disagreed depending on which
     one had been used. The breadcrumb trail offered the current page as its own parent,
     and the workflow rail offered the open screen as a step to travel to.

     `/applications/:id` is the survivor because it is the address the board rows, the
     search palette, the intake redirect and the duplicate list all build - making the
     other one canonical would have bounced the majority of navigation through a redirect
     - and because it stays honest if what this screen does changes again. */
  application,
  resumeApplication: (applicationId: string): string => `${application(applicationId)}/resume`,
  draft: (applicationId: string): string => `${application(applicationId)}/draft`,
  revision: (revisionId: string): string => `/revisions/${segment(revisionId)}`,
} as const;
