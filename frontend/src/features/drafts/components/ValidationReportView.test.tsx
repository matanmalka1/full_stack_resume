import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { ValidationReportView } from "./ValidationReportView";

describe("ValidationReportView", () => {
  it("uses Hebrew copy for a known issue code and hides raw validation prose", () => {
    render(
      <ValidationReportView
        report={{
          passed: false,
          groups: { content: false },
          evidence: {},
          issues: [
            {
              group: "content",
              code: "unsupported-derived-claim",
              hard: true,
              message: "extractive derived wording must link exactly one canonical fact",
            },
          ],
        }}
      />,
    );

    expect(screen.getByText("הניסוח שנגזר אינו נתמך באופן מלא בעובדה המקושרת.")).toBeInTheDocument();
    expect(screen.queryByText(/extractive derived wording/)).not.toBeInTheDocument();
  });

  it("keeps safe detail for an issue code the client does not know", () => {
    render(
      <ValidationReportView
        report={{
          passed: false,
          groups: { future: false },
          evidence: {},
          issues: [{ group: "future", code: "future-check", hard: true, message: "Safe future explanation." }],
        }}
      />,
    );

    expect(screen.getByText("Safe future explanation.")).toBeInTheDocument();
  });
});
