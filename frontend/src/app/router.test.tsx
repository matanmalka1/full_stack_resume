import { isValidElement } from "react";
import { describe, expect, it } from "vitest";

import { NewApplicationPage } from "@/features/application-intake";
import { ApplicationListPage } from "@/features/application-list";
import { ApplicationPage } from "@/features/applications";
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

  /* One address, one screen. `/preparation` was a second name for this same screen, and
     the two components that locate the reader by comparing against `pathname` disagreed
     depending on which one had been used to arrive. It is a redirect now, so the
     assertion is that the hub answers its own address and nothing else does. */
  it("answers the Application address with the hub screen and redirects its former name", () => {
    expect(elementType("applications/:applicationId")).toBe(ApplicationPage);
    expect(elementType("applications/:applicationId/preparation")).not.toBe(ApplicationPage);
    expect(route("applications/:applicationId/preparation")).not.toBeUndefined();
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
    const redirects = screens.filter((entry) =>
      isValidElement(entry.element) && typeof entry.element.type === "function"
        ? entry.element.type.name.endsWith("Redirect")
        : false,
    );

    expect(redirects.map((entry) => entry.path)).toEqual([
      "applications/:applicationId/preparation",
      "applications/:applicationId/tracking",
      "approved-revisions/:revisionId/ready",
    ]);
  });
});
