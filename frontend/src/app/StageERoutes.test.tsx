import { isValidElement } from "react";
import { describe, expect, it } from "vitest";

import { DraftEditorPage } from "../pages/DraftEditorPage";
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

});
