import { isValidElement } from "react";
import { describe, expect, it } from "vitest";

import { NewApplicationPage } from "@/features/application-intake";
import { ApplicationListPage } from "@/features/application-list";
import { JobDetailsPage } from "@/features/applications";
import { router } from "./router";

const route = (path: string) => router.routes[0]?.children?.find((entry) => entry.path === path);
const elementType = (path: string) => {
  const element = route(path)?.element;
  return isValidElement(element) ? element.type : null;
};

describe("the route table", () => {
  it("puts the board at the root and intake on its own path", () => {
    const index = router.routes[0]?.children?.find((entry) => entry.index === true);

    expect(isValidElement(index?.element) ? index?.element.type : null).toBe(ApplicationListPage);
    expect(elementType("applications/new")).toBe(NewApplicationPage);
  });

  /* Two addresses, one screen, on purpose: `/preparation` names the document workflow
     that links and bookmarks point at directly. */
  it("answers both Application addresses with the hub screen", () => {
    expect(elementType("applications/:applicationId")).toBe(JobDetailsPage);
    expect(elementType("applications/:applicationId/preparation")).toBe(JobDetailsPage);
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

  /* Every path that is not a screen redirects rather than rendering something. Derived
     from the table, so a route added as a redirect is checked without anyone registering
     it here. */
  it("keeps the compatibility paths as redirects", () => {
    const redirects = (router.routes[0]?.children ?? []).filter((entry) =>
      isValidElement(entry.element) && typeof entry.element.type === "function"
        ? entry.element.type.name.endsWith("Redirect")
        : false,
    );

    expect(redirects.map((entry) => entry.path)).toEqual([
      "applications/:applicationId/tracking",
      "approved-revisions/:revisionId/ready",
    ]);
  });
});
