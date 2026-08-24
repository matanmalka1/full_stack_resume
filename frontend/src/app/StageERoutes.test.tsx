import { isValidElement } from "react";
import { describe, expect, it } from "vitest";

import { ApprovalPage } from "../pages/ApprovalPage";
import { ReadyPage } from "../pages/ReadyPage";
import { RenderPage } from "../pages/RenderPage";
import { SettingsPage } from "../pages/SettingsPage";
import { ValidationPage } from "../pages/ValidationPage";
import { router } from "./router";

const stageERoute = (path: string) => router.routes[0]?.children?.find((route) => route.path === path);
const stageEElementType = (path: string) => {
  const element = stageERoute(path)?.element;
  return isValidElement(element) ? element.type : null;
};

describe("Stage E routes", () => {
  it("mounts ValidationPage at the validation path", () => {
    expect(stageEElementType("applications/:applicationId/validation")).toBe(ValidationPage);
  });

  it("mounts ApprovalPage at the approval path", () => {
    expect(stageEElementType("applications/:applicationId/approval")).toBe(ApprovalPage);
  });

  it("mounts RenderPage for an exact approved revision", () => {
    expect(stageEElementType("approved-revisions/:approvedRevisionId/render")).toBe(RenderPage);
  });

  it("mounts ReadyPage for an exact approved revision", () => {
    expect(stageEElementType("approved-revisions/:approvedRevisionId/ready")).toBe(ReadyPage);
  });

  it("mounts SettingsPage at the settings path", () => {
    expect(stageEElementType("settings")).toBe(SettingsPage);
  });

});
