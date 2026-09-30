import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, within } from "@testing-library/react";
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
      shortfallSeverity: null,
      shortfallReason: null,
      rationale: null,
      supportingFactIds: [],
      boundaryFactIds: [],
    },
    {
      requirementId: "requirement-2",
      text: "Fluent English",
      importance: "preferred",
      coverage: "matched",
      shortfallSeverity: null,
      shortfallReason: null,
      rationale: null,
      supportingFactIds: [],
      boundaryFactIds: [],
    },
  ],
  unreadableRequirementCount: 0,
  issues: [],
  sourceCoverage: 1,
};

const renderPanel = (value: Classification) => {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={client}>
      <AnalysisPanel classification={value} detail={detail()} />
    </QueryClientProvider>,
  );
};

describe("AnalysisPanel", () => {
  it("leads with the role summary and splits coverage by mandatory and preferred asks", () => {
    renderPanel(classification);

    expect(screen.getByRole("heading", { name: "מה המשרה מחפשת" })).toBeInTheDocument();
    expect(screen.getByText("A cloud sales role.")).toBeInTheDocument();
    const overview = screen.getByRole("region", { name: "סיכום הכיסוי" });
    expect(within(overview).getByText("0/1")).toBeInTheDocument();
    expect(within(overview).getByText("פער קשיח אחד")).toBeInTheDocument();
    expect(within(overview).getByText("1/1")).toBeInTheDocument();
    /* The classification and the verdict belong to the matching form and the step
       banner; the panel does not restate either. */
    expect(screen.queryByText("סיווג שהוצע")).not.toBeInTheDocument();
    expect(screen.queryByText("התאמה נמוכה")).not.toBeInTheDocument();
  });

  it("opens on the requirements needing attention, each shown once with its reason", () => {
    renderPanel(classification);

    const mandatory = screen.getByRole("list", { name: "דרישות חובה" });
    expect(
      within(mandatory).getByRole("heading", { name: "Experience selling AWS-based solutions" }),
    ).toBeInTheDocument();
    expect(screen.getAllByText("Experience selling AWS-based solutions")).toHaveLength(1);
    expect(screen.getByText("Canonical facts do not verify this requirement.")).toBeInTheDocument();
    expect(screen.queryByText("Fluent English")).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "הכל (2)" }));
    expect(screen.getByRole("list", { name: "דרישות מועדפות" })).toBeInTheDocument();
    expect(screen.getByText("Fluent English")).toBeInTheDocument();
  });

  it("shows a minor mandatory shortfall with its own severity, reason and the AI's rationale", () => {
    renderPanel({
      ...classification,
      fit: "high",
      gaps: [{ ...classification.gaps[0], severity: "warning" }],
      requirements: [
        {
          ...classification.requirements[0],
          coverage: "partial",
          shortfallSeverity: "minor",
          shortfallReason: "The verified duration is slightly below the requested threshold.",
          rationale: "AWS work is verified, but not for the requested duration.",
        },
      ],
    });

    expect(screen.getByText("ללא פער קשיח")).toBeInTheDocument();
    expect(screen.getByText(/פער קטן:/)).toBeInTheDocument();
    expect(screen.getByText(/verified duration is slightly below/)).toBeInTheDocument();
    expect(screen.getByText(/הסבר ה-AI:/)).toBeInTheDocument();
    expect(screen.getByText("AWS work is verified, but not for the requested duration.")).toBeInTheDocument();
  });
});
