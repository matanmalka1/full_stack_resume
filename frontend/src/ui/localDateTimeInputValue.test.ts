import { describe, expect, it } from "vitest";

import { isoFromLocalDateTimeInput } from "./isoFromLocalDateTimeInput";
import { localDateTimeInputValue } from "./localDateTimeInputValue";

describe("localDateTimeInputValue", () => {
  it("formats local date parts for a datetime-local input", () => {
    expect(localDateTimeInputValue(new Date(2026, 0, 2, 3, 4))).toBe("2026-01-02T03:04");
  });
});

describe("isoFromLocalDateTimeInput", () => {
  it("returns null instead of throwing for an invalid local value", () => {
    expect(isoFromLocalDateTimeInput("not-a-date")).toBeNull();
  });

  it("converts a valid local value to ISO", () => {
    expect(isoFromLocalDateTimeInput("2026-09-01T12:30")).toBe(new Date("2026-09-01T12:30").toISOString());
  });
});
