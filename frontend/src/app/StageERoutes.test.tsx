import { isValidElement } from "react";
import { describe, expect, it } from "vitest";

import { ApplicationListPage } from "../pages/ApplicationListPage";
import { NewApplicationPage } from "../pages/NewApplicationPage";
import { router } from "./router";

const stageERoute = (path: string) => router.routes[0]?.children?.find((route) => route.path === path);
const stageEElementType = (path: string) => {
  const element = stageERoute(path)?.element;
  return isValidElement(element) ? element.type : null;
};

describe("Stage E routes", () => {
  /* Validation, approval, and render are states of the draft editor, so the route
     table must not carry a screen for any of them. Keeping the assertion as "no route"
     rather than deleting it means a re-added interstitial fails here. */
  it("keeps validation, approval, and render off the route table", () => {
    expect(stageERoute("applications/:applicationId/validation")).toBeUndefined();
    /* Review joined them: the analysis it decides about is on the Application screen, so
       a separate route showed the subject in one place and the controls in another. */
    expect(stageERoute("applications/:applicationId/review")).toBeUndefined();
    expect(stageERoute("applications/:applicationId/approval")).toBeUndefined();
    expect(stageERoute("approved-revisions/:approvedRevisionId/render")).toBeUndefined();
    /* Render is a step of the editor, and the revision it produced is addressed by the
       revision rather than by a state name. */
    expect(stageERoute("revisions/:revisionId/render")).toBeUndefined();
  });

  /* The recruitment axis is a view of the Application screen, not a route. Asserted as
     absence for the same reason as the four above: re-adding a screen for it puts the
     masthead, the projection read, and the error handling back in two places. */
  it("keeps the recruitment axis off the route table as a screen", () => {
    const element = stageERoute("applications/:applicationId/tracking")?.element;
    const name =
      isValidElement(element) && typeof element.type === "function" ? element.type.name : null;
    /* The path itself stays - it answers older bookmarks - but only as the redirect. */
    expect(name).toBe("TrackingRedirect");
  });

  it("puts the Application list at the root and intake on its own path", () => {
    const index = router.routes[0]?.children?.find((route) => route.index === true);
    expect(isValidElement(index?.element) ? index?.element.type : null).toBe(ApplicationListPage);
    expect(stageEElementType("applications/new")).toBe(NewApplicationPage);
  });
});

/* Route components that are not screens, and so publish no workflow stage.

   A list of deliberate exceptions rather than a filter on the check: a screen that
   forgets `useWorkflowStage` must fail below, and it only escapes by being named here on
   purpose. A redirect renders nothing and unmounts immediately, so publishing a stage
   from one would announce a landmark for a screen the reader never sees. */
const NON_SCREEN_ROUTE_COMPONENTS = new Set(["TrackingRedirect", "ReadyRedirect"]);

/* The pages the route table actually mounts, derived from the table rather than listed
   here. A route added to `router.tsx` joins this set without anyone remembering to
   register it, which is the point: the check below fails for the new screen rather than
   passing because a list was not updated. */
const routeComponentNames = (): string[] => {
  const names = (router.routes[0]?.children ?? []).map((route) =>
    isValidElement(route.element) && typeof route.element.type === "function"
      ? route.element.type.name
      : null,
  );
  /* A route whose element is not a named function component is a hole in the derivation,
     not something to pass over quietly. */
  expect(names).not.toContain(null);
  return [...new Set(names as string[])].filter(
    (name) => !NON_SCREEN_ROUTE_COMPONENTS.has(name),
  );
};

describe("workflow stage publishing", () => {
  /* `useWorkflowStage` has no unmount reset: resetting there produced a flash of `intake`
     between two screens that were both mid-workflow. That trade makes publishing
     mandatory - a screen that publishes nothing inherits whatever stage the previous one
     left behind, so Settings could sit under a landmark still claiming "אימות".

     Nothing in the types says so, so the guard is derived here. It reads each page's
     source rather than rendering it, because what is being checked is that the call
     exists at all, which needs no query client, router context, or server.

     The sources come through Vite rather than `node:fs`: the app's TypeScript project
     deliberately carries no Node types, and this check needs none. */
  const pageSources = import.meta.glob("../pages/**/*.tsx", {
    query: "?raw",
    import: "default",
    eager: true,
  }) as Record<string, string>;

  it("requires every routed screen to publish a workflow stage", () => {
    for (const name of routeComponentNames()) {
      const matches = Object.entries(pageSources).filter(([path]) =>
        path.endsWith(`/${name}.tsx`),
      );
      /* A route component with no file of that name means the derivation stopped matching
         the pages, which is a failure here rather than a silently skipped check. More
         than one match is equally ambiguous, so nested page folders do not weaken the
         one routed component -> one source contract. */
      expect(matches).toHaveLength(1);
      const source = matches[0]?.[1];
      expect(source).toBeDefined();
      expect(source).toMatch(/useWorkflowStage\(/);
    }
  });
});
