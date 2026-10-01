import { isValidElement } from "react";
import type { RouteObject } from "react-router-dom";
import { describe, expect, it } from "vitest";

import { NewApplicationPage } from "@/features/application-intake/pages/NewApplicationPage";
import { ApplicationListPage } from "@/features/application-list/pages/ApplicationListPage";
import { ApplicationPage } from "@/features/application-detail/pages/ApplicationPage";
import { ApplicationResumePage } from "@/features/application-detail/pages/ApplicationResumePage";
import { DraftEditorPage } from "@/features/drafts/pages/DraftEditorPage";
import { ReadyPage } from "@/features/ready/pages/ReadyPage";
import { RootRouteErrorBoundary, RouteErrorBoundary } from "./layout/RouteErrorBoundary";
import { routes } from "./router";

/* Every screen sits under a pathless route whose only job is to own the error boundary,
   so the table is read one level in. Reading `routes[0].children` directly would find
   that single wrapper and report every screen as absent. */
const screens = routes[0]?.children?.[0]?.children ?? [];
const route = (path: string) => screens.find((entry) => entry.path === path);

/* Screens are loaded on first visit, so a route names its screen through `lazy` rather
   than `element`. The table is read as declared rather than through the live router,
   which rewrites a route's `lazy` in place once it starts loading that screen. */
const screenOf = async (entry: RouteObject | undefined) => {
  const lazy = entry?.lazy;
  return typeof lazy === "function" ? ((await lazy()).Component ?? null) : null;
};
const elementType = (path: string) => screenOf(route(path));

describe("the route table", () => {
  it("puts the board at the root and intake on its own path", async () => {
    const index = screens.find((entry) => entry.index === true);

    expect(await screenOf(index)).toBe(ApplicationListPage);
    expect(await elementType("applications/new")).toBe(NewApplicationPage);
  });

  it("keeps root and in-layout failures in containers that own different landmarks", () => {
    const rootBoundary = routes[0]?.errorElement;
    const routeBoundary = routes[0]?.children?.[0]?.errorElement;

    expect(isValidElement(rootBoundary) ? rootBoundary.type : null).toBe(RootRouteErrorBoundary);
    expect(isValidElement(routeBoundary) ? routeBoundary.type : null).toBe(RouteErrorBoundary);
  });

  /* One address, one screen. `/preparation` was a second name for this same screen, and
     the two components that locate the reader by comparing against `pathname` disagreed
     depending on which one had been used to arrive. */
  it("answers only the canonical Application addresses", async () => {
    expect(await elementType("applications/:applicationId")).toBe(ApplicationPage);
    expect(await elementType("applications/:applicationId/resume")).toBe(ApplicationResumePage);
    expect(route("applications/:applicationId/preparation")).toBeUndefined();
    expect(route("applications/:applicationId/tracking")).toBeUndefined();
    expect(route("approved-revisions/:revisionId/ready")).toBeUndefined();
  });

  /* One document per Application: the editor and the ready step are both addressed by the
     Application, and no screen is addressed by a revision any more - there are none. */
  it("addresses the draft and ready steps by the Application", async () => {
    expect(await elementType("applications/:applicationId/draft")).toBe(DraftEditorPage);
    expect(await elementType("applications/:applicationId/ready")).toBe(ReadyPage);
    expect(route("revisions/:revisionId")).toBeUndefined();
    expect(route("revisions/:revisionId/compare")).toBeUndefined();
  });

  /* Checking, approval, review, and render are states of the draft editor, so the table
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
