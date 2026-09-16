import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import type { Classification } from "@/api/analyses";
import { AnalysisStatusBanner } from "./AnalysisStatusBanner";

const classification = (fit: Classification["fit"]): Classification => ({
  track: "sales",
  profile: "account-executive",
  emphasis: "tech-consultative-sales",
  language: "en",
  fit,
  fitScore: fit === "low" ? 0.26 : null,
  gaps: [],
  decided: [],
  summary: null,
  keywords: [],
  requirements: [],
  unreadableRequirementCount: 0,
  issues: [],
  sourceCoverage: null,
});

describe("AnalysisStatusBanner", () => {
  it.each(["low", "unknown"] as const)(
    "presents %s Fit as diagnostic rather than an approval gate",
    (fit) => {
      render(<AnalysisStatusBanner classification={classification(fit)} supersededAnalysis={false} />);

      expect(screen.getByText(/אפשר להמשיך ליצירת טיוטה/)).toBeInTheDocument();
      expect(screen.queryByText(/אישור|הכרעה/)).not.toBeInTheDocument();
    },
  );
});
