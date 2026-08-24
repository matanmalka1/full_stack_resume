import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import type { ValidationReport } from "../api/contracts";
import { ValidationReportView } from "./ValidationReportView";

const report = (overrides: Partial<ValidationReport> = {}): ValidationReport => ({
  passed: true,
  groups: {},
  evidence: {},
  issues: [],
  ...overrides,
});

describe("ValidationReportView", () => {
  it("shows a success result when no issues exist", () => {
    render(<ValidationReportView report={report()} />);
    expect(screen.getByText("לא נמצאו חסימות או אזהרות")).toBeInTheDocument();
  });

  it("distinguishes a hard issue from a warning in text and tone", () => {
    render(<ValidationReportView report={report({ issues: [
      { group: "facts", code: "HARD", hard: true, message: "Blocked" },
      { group: "copy", code: "SOFT", hard: false, message: "Review" },
    ] })} />);
    expect(screen.getByText("Blocked").closest(".rounded-surface")).toHaveTextContent("חסימה");
    expect(screen.getByText("Review").closest(".rounded-surface")).toHaveTextContent("אזהרה");
    expect(screen.getByText("Blocked").closest(".rounded-surface")).toHaveTextContent("הריצו אימות מחדש");
  });

  it("gives unsupported claims their specific safe resolution", () => {
    render(<ValidationReportView report={report({ passed: false, issues: [
      { group: "content", code: "unlinked-claim", hard: true, message: "Unsupported text" },
    ] })} />);
    expect(screen.getByText(/קשרו את הטענה לעובדה מאושרת/)).toBeInTheDocument();
    expect(screen.getByText(/או הסירו את הטענה/)).toBeInTheDocument();
  });

  it("preserves unknown group and issue codes in technical details", () => {
    render(<ValidationReportView report={report({ issues: [{ group: "future", code: "FUTURE_CODE", hard: true, message: "Future" }] })} />);
    expect(screen.getByText("future · FUTURE_CODE")).toBeInTheDocument();
  });

  it("preserves arbitrary evidence rather than projecting a known subset", () => {
    render(<ValidationReportView report={report({ evidence: { future_key: { nested: 7 } } })} />);
    expect(screen.getByText(/future_key/)).toBeInTheDocument();
    expect(screen.getByText(/nested/)).toBeInTheDocument();
  });
});
