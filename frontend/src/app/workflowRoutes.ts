import { useMatch } from "react-router-dom";

/* Which routes are steps of the CV wizard, for the shell that draws itself differently
   inside one.

   The patterns are written out rather than built from `routePaths`, because `routePaths`
   percent-encodes its id argument - it exists to make an id with a slash stay one segment
   - and a pattern is not an id. `workflowRoutes.test.ts` pins the list against the paths
   `router.tsx` actually declares, so a route that moves fails there instead of quietly
   dropping a step back into the dashboard chrome. */
const workflowPatterns = [
  "/applications/new",
  "/applications/:applicationId",
  "/applications/:applicationId/draft",
  "/revisions/:revisionId",
] as const;

/* One hook per pattern, in a fixed order, which is what the rules of hooks require: the
   list is a module constant, so the same calls happen in the same order on every render. */
export const useInWorkflow = (): boolean => {
  const intake = useMatch(workflowPatterns[0]);
  const preparation = useMatch(workflowPatterns[1]);
  const draft = useMatch(workflowPatterns[2]);
  const revision = useMatch(workflowPatterns[3]);

  return intake !== null || preparation !== null || draft !== null || revision !== null;
};

export const workflowRoutePatterns = workflowPatterns;
