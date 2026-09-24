import { describe, expect, it } from "vitest";

import { formatUsd } from "./formatUsd";

describe("formatUsd", () => {
  it.each([
    ["0.00002806", "$0.000028"],
    ["0.0049", "$0.0049"],
    ["0.012", "$0.01"],
    ["1.5", "$1.50"],
    ["1234.567", "$1,234.57"],
    ["0", "$0"],
    ["not-a-number", "$not-a-number"],
  ])("formats %s as %s", (value, expected) => {
    expect(formatUsd(value)).toBe(expected);
  });
});
