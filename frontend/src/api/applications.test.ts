import { describe, expect, it } from "vitest";

import { acknowledgementApplies, duplicateMatchesFromProblem } from "./applications";
import { ApiProblem, type ProblemDetails } from "./client";
import type { ApplicationIntake } from "./contracts";

const intake = (overrides: Partial<ApplicationIntake> = {}): ApplicationIntake => ({
  company: "Acme",
  target_role: "Backend Engineer",
  job_text: "Job description text",
  source_url: null,
  ...overrides,
});

const problem = (overrides: Partial<ProblemDetails> = {}): ApiProblem =>
  new ApiProblem({
    type: "about:blank#duplicate_acknowledgement_required",
    title: "Precondition Failed",
    status: 412,
    code: "DUPLICATE_ACKNOWLEDGEMENT_REQUIRED",
    detail: "possible duplicate applications require explicit acknowledgement",
    ...overrides,
  });

const match = (matchedOn: string[] = ["company_title"]) => ({
  application_id: "app-existing",
  company: "Acme",
  target_role: "Backend Engineer",
  matched_on: matchedOn,
});

describe("acknowledgementApplies", () => {
  it("refuses an acknowledgement that answers nothing", () => {
    expect(acknowledgementApplies(undefined, intake())).toBe(false);
  });

  it("accepts an acknowledgement given for the same intake", () => {
    expect(acknowledgementApplies(intake(), intake())).toBe(true);
  });

  it("refuses an acknowledgement once any part of the intake moved", () => {
    expect(acknowledgementApplies(intake(), intake({ job_text: "Another posting" }))).toBe(false);
    expect(acknowledgementApplies(intake(), intake({ company: "Acme Ltd" }))).toBe(false);
    expect(acknowledgementApplies(intake(), intake({ target_role: "Data Engineer" }))).toBe(false);
    expect(
      acknowledgementApplies(intake(), intake({ source_url: "https://example.com/jobs/1" })),
    ).toBe(false);
  });
});

describe("duplicateMatchesFromProblem", () => {
  it("ignores anything that is not the duplicate refusal", () => {
    expect(duplicateMatchesFromProblem(new Error("network"))).toBeNull();
    expect(duplicateMatchesFromProblem(problem({ code: "PRECONDITION_FAILED" }))).toBeNull();
  });

  it("reads the candidates the create command named", () => {
    const matches = duplicateMatchesFromProblem(problem({ context: { matches: [match()] } }));

    expect(matches).toEqual([match()]);
  });

  /* An empty list still has to reach the screen: the server refused for duplicates and
     the explicit create-anyway path is the only way forward, named candidates or not. */
  it("reports a refusal that named no candidates as empty rather than absent", () => {
    expect(duplicateMatchesFromProblem(problem())).toEqual([]);
    expect(duplicateMatchesFromProblem(problem({ context: { matches: "none" } }))).toEqual([]);
  });

  it("drops a candidate carrying a detection reason the union does not know", () => {
    const context = { matches: [match(["company_title"]), match(["telepathy"])] };

    expect(duplicateMatchesFromProblem(problem({ context }))).toEqual([match(["company_title"])]);
  });
});
