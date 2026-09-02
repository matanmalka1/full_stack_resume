import { describe, expect, it } from "vitest";

import { appRoutes } from "./appRoutes";

describe("appRoutes", () => {
  it("encodes identifiers as one path segment for every record route", () => {
    const id = "record / עברית";

    expect(appRoutes.application(id)).toBe("/applications/record%20%2F%20%D7%A2%D7%91%D7%A8%D7%99%D7%AA");
    expect(appRoutes.preparation(id)).toBe("/applications/record%20%2F%20%D7%A2%D7%91%D7%A8%D7%99%D7%AA/preparation");
    expect(appRoutes.draft(id)).toBe("/applications/record%20%2F%20%D7%A2%D7%91%D7%A8%D7%99%D7%AA/draft");
    expect(appRoutes.revision(id)).toBe("/revisions/record%20%2F%20%D7%A2%D7%91%D7%A8%D7%99%D7%AA");
  });
});
