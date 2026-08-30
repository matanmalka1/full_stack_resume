import { isValidElement } from "react";
import { describe, expect, it } from "vitest";

import { ApplicationListPage } from "../pages/ApplicationListPage";
import { DraftEditorPage } from "../pages/DraftEditorPage";
import { NewApplicationPage } from "../pages/NewApplicationPage";
import { ReadyPage } from "../pages/ReadyPage";
import { SettingsPage } from "../pages/SettingsPage";
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
  });

  it("mounts the draft editor, which owns validation and approval", () => {
    expect(stageEElementType("applications/:applicationId/draft")).toBe(DraftEditorPage);
  });

  it("mounts ReadyPage for an exact approved revision", () => {
    expect(stageEElementType("approved-revisions/:approvedRevisionId/ready")).toBe(ReadyPage);
  });

  it("mounts SettingsPage at the settings path", () => {
    expect(stageEElementType("settings")).toBe(SettingsPage);
  });

  /* The root is the list and intake is a screen reached from it. Asserted as a pair
     because swapping them back is exactly the regression that made an existing
     Application reachable only by its URL. */
  it("puts the Application list at the root and intake on its own path", () => {
    const index = router.routes[0]?.children?.find((route) => route.index === true);
    expect(isValidElement(index?.element) ? index?.element.type : null).toBe(ApplicationListPage);
    expect(stageEElementType("applications/new")).toBe(NewApplicationPage);
  });
});

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
  return [...new Set(names as string[])];
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
  const pageSources = import.meta.glob("../pages/*.tsx", {
    query: "?raw",
    import: "default",
    eager: true,
  }) as Record<string, string>;

  it.each(routeComponentNames())("%s publishes a workflow stage", (name) => {
    const source = pageSources[`../pages/${name}.tsx`];
    /* A route component with no file of that name means the derivation stopped matching
       the pages, which is a failure here rather than a silently skipped check. */
    expect(source).toBeDefined();
    expect(source).toMatch(/useWorkflowStage\(/);
  });
});
