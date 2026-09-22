import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
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
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    render(
      <QueryClientProvider client={client}>
        <AnalysisPanel classification={classification} detail={detail()} />
      </QueryClientProvider>,
    );

    expect(screen.queryByText("פערים מול העובדות")).not.toBeInTheDocument();
    expect(screen.getByText("דרישות המשרה וכיסויין")).toBeInTheDocument();
    expect(screen.getByRole("list", { name: "דורשות תשומת לב (1)" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Experience selling AWS-based solutions" })).toBeInTheDocument();
    expect(screen.getAllByText("Experience selling AWS-based solutions")).toHaveLength(1);
    expect(screen.getByText("Canonical facts do not verify this requirement.")).toBeInTheDocument();
    expect(screen.queryByText("לא סופק הסבר מפורט לפער.")).not.toBeInTheDocument();
  });

  it("shows a minor mandatory shortfall as attention rather than a hard gap", () => {
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    const minor: Classification = {
      ...classification,
      fit: "high",
      gaps: [{ ...classification.gaps[0], severity: "warning" }],
      requirements: [
        {
          ...classification.requirements[0],
          coverage: "partial",
          shortfallSeverity: "minor",
          shortfallReason: "The verified duration is slightly below the requested threshold.",
        },
      ],
    };

    render(
      <QueryClientProvider client={client}>
        <AnalysisPanel classification={minor} detail={detail()} />
      </QueryClientProvider>,
    );

    expect(screen.getByText("דרישת חובה אחת דורשת תשומת לב, ללא פער קשיח.")).toBeInTheDocument();
    expect(screen.getByText(/פער קטן:/)).toBeInTheDocument();
    expect(screen.getByText(/verified duration is slightly below/)).toBeInTheDocument();
  });
});
