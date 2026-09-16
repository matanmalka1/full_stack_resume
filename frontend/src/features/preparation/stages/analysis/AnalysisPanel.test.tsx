import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import type { Classification } from "@/api/analyses";
import { detail } from "@/test/fixtures";
import { AnalysisPanel } from "./AnalysisPanel";

const classification: Classification = {
  track: "sales",
  profile: "account-executive",
  emphasis: "tech-consultative-sales",
  language: "en",
  fit: "low",
  fitScore: 0.26,
  gaps: [
    {
      requirementId: "requirement-1",
      requirement: "Experience selling AWS-based solutions",
      severity: "hard",
      reason: "Canonical facts do not verify this requirement.",
      substituteFactIds: [],
    },
  ],
  decided: [],
  summary: "A cloud sales role.",
  keywords: ["AWS"],
  requirements: [
    {
      requirementId: "requirement-1",
      text: "Experience selling AWS-based solutions",
      importance: "mandatory",
      coverage: "unsupported",
      supportingFactIds: [],
      boundaryFactIds: [],
    },
  ],
  unreadableRequirementCount: 0,
  issues: [],
  sourceCoverage: 1,
};

describe("AnalysisPanel", () => {
  it("shows each unmet requirement once in the complete coverage view", () => {
    render(<AnalysisPanel classification={classification} detail={detail()} />);

    expect(screen.queryByText("פערים מול העובדות")).not.toBeInTheDocument();
    expect(screen.getByText("דרישות המשרה וכיסויין")).toBeInTheDocument();
    expect(screen.getByRole("list", { name: "פירוט כיסוי דרישות המשרה" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Experience selling AWS-based solutions" })).toBeInTheDocument();
    expect(screen.getAllByText("Experience selling AWS-based solutions")).toHaveLength(1);
  });
});
