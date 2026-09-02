import { describe, expect, it } from "vitest";

import { localDateTimeInputValue } from "./localDateTimeInputValue";

describe("localDateTimeInputValue", () => {
  it("formats local date parts for a datetime-local input", () => {
    expect(localDateTimeInputValue(new Date(2026, 0, 2, 3, 4))).toBe("2026-01-02T03:04");
  });
});
