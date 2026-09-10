import { describe, expect, it } from "vitest";

import { routePaths } from "./routePaths";

describe("routePaths", () => {
  it("encodes identifiers as one path segment for every record route", () => {
    const id = "record / עברית";

    expect(routePaths.application(id)).toBe("/applications/record%20%2F%20%D7%A2%D7%91%D7%A8%D7%99%D7%AA");
    expect(routePaths.resumeApplication(id)).toBe("/applications/record%20%2F%20%D7%A2%D7%91%D7%A8%D7%99%D7%AA/resume");
    expect(routePaths.draft(id)).toBe("/applications/record%20%2F%20%D7%A2%D7%91%D7%A8%D7%99%D7%AA/draft");
    expect(routePaths.revision(id)).toBe("/revisions/record%20%2F%20%D7%A2%D7%91%D7%A8%D7%99%D7%AA");
  });
});
