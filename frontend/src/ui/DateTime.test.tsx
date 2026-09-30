import { render } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { DateTime } from "./DateTime";

describe("DateTime", () => {
  it("keeps the Hebrew month right-to-left and isolates numeric styles left-to-right", () => {
    const { container } = render(
      <p dir="rtl">
        <DateTime value="2026-09-30T19:33:00Z" />
        <DateTime format="short" value="2026-09-30T19:33:00Z" />
      </p>,
    );
    const [medium, short] = [...container.querySelectorAll("bdi")];
    /* "30 בספט׳ 2026, 22:33" forced left-to-right put the month after the time. */
    expect(medium).toHaveAttribute("dir", "rtl");
    expect(medium?.querySelector("time")).toHaveAttribute("dateTime", "2026-09-30T19:33:00Z");
    expect(short).toHaveAttribute("dir", "ltr");
  });
});
