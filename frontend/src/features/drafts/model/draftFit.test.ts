import { describe, expect, it } from "vitest";

import type { ApplicationDetail } from "@/api/contracts";
import { detail } from "@/test/records";
import { draftFit } from "./draftFit";

const requirement = (id: string, coverage: string) => ({
  requirement_id: id,
  text: `Requirement ${id}`,
  importance: "mandatory",
  coverage,
});

const withAnalysis = (overrides: Record<string, unknown> = {}): ApplicationDetail => {
  const base = detail();
  return detail({
    latest_analysis: {
      id: base.latest_analysis_id,
      job_text_hash: base.job_text_hash,
      created_at: "2026-09-10T08:00:00Z",
      fit_level: "good",
      fit_score: 0.5,
      analysis: {
        requirements: [requirement("r1", "matched"), requirement("r2", "partial"), requirement("r3", "unsupported")],
      },
      gaps: [
        { requirement_id: "r2", requirement: "Requirement r2", severity: "warning", reason: "partial" },
        { requirement_id: "r3", requirement: "Requirement r3", severity: "hard", reason: "missing" },
      ],
      ...overrides,
    } as unknown as ApplicationDetail["latest_analysis"],
  });
};

describe("draftFit", () => {
  it("counts only met requirements and lists demanded gaps first", () => {
    expect(draftFit(withAnalysis())).toEqual({
      matched: 1,
      total: 3,
      gaps: [
        { requirementId: "r3", requirement: "Requirement r3", severity: "hard" },
        { requirementId: "r2", requirement: "Requirement r2", severity: "warning" },
      ],
    });
  });

  it("says nothing about an analysis of a posting the Application no longer holds", () => {
    expect(draftFit(withAnalysis({ job_text_hash: "f".repeat(64) }))).toBeNull();
  });

  it("says nothing without an analysis or without requirements", () => {
    expect(draftFit(detail())).toBeNull();
    expect(draftFit(withAnalysis({ analysis: { requirements: [] } }))).toBeNull();
  });
});
