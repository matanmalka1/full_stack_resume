import { isValidElement } from "react";
import { describe, expect, it } from "vitest";

import { NewApplicationPage } from "@/features/application-intake";
import { ApplicationListPage } from "@/features/application-list";
import { ApplicationPage, ApplicationResumePage } from "@/features/applications";
import { RootRouteErrorBoundary, RouteErrorBoundary } from "./layout/RouteErrorBoundary";
import { router } from "./router";

/* Every screen sits under a pathless route whose only job is to own the error boundary,
   so the table is read one level in. Reading `routes[0].children` directly would find
   that single wrapper and report every screen as absent. */
const screens = router.routes[0]?.children?.[0]?.children ?? [];
const route = (path: string) => screens.find((entry) => entry.path === path);
const elementType = (path: string) => {
  const element = route(path)?.element;
  return isValidElement(element) ? element.type : null;
};

describe("the route table", () => {
  it("puts the board at the root and intake on its own path", () => {
    const index = screens.find((entry) => entry.index === true);

    expect(isValidElement(index?.element) ? index?.element.type : null).toBe(ApplicationListPage);
    expect(elementType("applications/new")).toBe(NewApplicationPage);
  });

  it("keeps root and in-layout failures in containers that own different landmarks", () => {
    const rootBoundary = router.routes[0]?.errorElement;
    const routeBoundary = router.routes[0]?.children?.[0]?.errorElement;

    expect(isValidElement(rootBoundary) ? rootBoundary.type : null).toBe(RootRouteErrorBoundary);
    expect(isValidElement(routeBoundary) ? routeBoundary.type : null).toBe(RouteErrorBoundary);
  });

  /* One address, one screen. `/preparation` was a second name for this same screen, and
     the two components that locate the reader by comparing against `pathname` disagreed
     depending on which one had been used to arrive. */
  it("answers only the canonical Application addresses", () => {
    expect(elementType("applications/:applicationId")).toBe(ApplicationPage);
    expect(elementType("applications/:applicationId/resume")).toBe(ApplicationResumePage);
    expect(route("applications/:applicationId/preparation")).toBeUndefined();
    expect(route("applications/:applicationId/tracking")).toBeUndefined();
    expect(route("approved-revisions/:revisionId/ready")).toBeUndefined();
  });

  /* Validation, approval, review, and render are states of the draft editor, so the table
     must not carry a screen for any of them. Keeping the assertion as "no route" rather
     than deleting it means a re-added interstitial fails here. */
  it("keeps validation, review, approval, and render off the route table", () => {
    expect(route("applications/:applicationId/validation")).toBeUndefined();
    expect(route("applications/:applicationId/review")).toBeUndefined();
    expect(route("applications/:applicationId/approval")).toBeUndefined();
    expect(route("approved-revisions/:approvedRevisionId/render")).toBeUndefined();
    expect(route("revisions/:revisionId/render")).toBeUndefined();
  });
});
