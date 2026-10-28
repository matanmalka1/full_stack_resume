import { describe, expect, it } from "vitest";

import type { Requirement } from "@/api/analyses";
import type { DraftClaim } from "@/api/contracts";
import type { DocumentOutline } from "@/api/documents";
import { requirementCoverage } from "./requirementCoverage";

const requirement = (requirementId: string, overrides: Partial<Requirement> = {}): Requirement => ({
  requirementId,
  text: requirementId,
  importance: "mandatory",
  coverage: "matched",
  shortfallSeverity: null,
  shortfallReason: null,
  rationale: null,
  supportingFactIds: [],
  boundaryFactIds: [],
  ...overrides,
});

const line = (claim_id: string, fact_ids: string[], style: DraftClaim["style"] = "bullet"): DraftClaim => ({
  claim_id,
  claim_type: "canonical",
  fact_ids,
  style,
  text: claim_id,
});

const outline = (claims: DraftClaim[], headline = line("h", [], "headline")): DocumentOutline => ({
  headline,
  contacts: [],
  sections: [{ name: "Experience", claims }],
});

describe("requirementCoverage", () => {
  it("counts a requirement in the draft when any one supporting fact is linked", () => {
    const summary = requirementCoverage(
      [requirement("r1", { supportingFactIds: ["f1", "f2"] })],
      outline([line("a", ["f2"])]),
    );
    expect(summary.rows[0]?.state).toBe("in_document");
    expect(summary.inDocument).toBe(1);
    expect(summary.warned).toBe(0);
  });

  it("reads links from the headline and contacts as well as section lines", () => {
    const summary = requirementCoverage(
      [requirement("r1", { supportingFactIds: ["f1"] })],
      outline([], line("h", ["f1"], "headline")),
    );
    expect(summary.rows[0]?.state).toBe("in_document");
  });

  it("marks a requirement whose supporting facts the draft does not link", () => {
    const summary = requirementCoverage(
      [requirement("r1", { supportingFactIds: ["f1"] })],
      outline([line("a", ["other"])]),
    );
    expect(summary.rows[0]).toMatchObject({ state: "not_in_document", warned: true });
  });

  it("warns only where the backend does: mandatory and covered", () => {
    const summary = requirementCoverage(
      [
        requirement("preferred", { importance: "preferred", supportingFactIds: ["f1"] }),
        requirement("unsupported", { coverage: "unsupported", supportingFactIds: ["f1"] }),
        requirement("partial", { coverage: "partial", supportingFactIds: ["f1"] }),
      ],
      outline([]),
    );
    expect(summary.rows.map((row) => [row.requirement.requirementId, row.warned])).toEqual([
      ["unsupported", false],
      ["partial", true],
      ["preferred", false],
    ]);
    expect(summary.warned).toBe(1);
  });

  it("names a requirement without supporting facts as a gap, not as missing from the draft", () => {
    const summary = requirementCoverage([requirement("r1", { coverage: "unsupported" })], outline([line("a", ["f1"])]));
    expect(summary.rows[0]).toMatchObject({ state: "no_facts", warned: false });
    expect(summary.evidenced).toBe(0);
  });

  it("follows the outline it is given, so an unsaved relink changes the answer", () => {
    const requirements = [requirement("r1", { supportingFactIds: ["f1"] })];
    expect(requirementCoverage(requirements, outline([line("a", ["f1"])])).inDocument).toBe(1);
    expect(requirementCoverage(requirements, outline([line("a", [])])).inDocument).toBe(0);
  });

  it("orders missing evidence first, then gaps, then what is in the draft", () => {
    const summary = requirementCoverage(
      [
        requirement("in", { supportingFactIds: ["f1"] }),
        requirement("gap", { coverage: "unsupported" }),
        requirement("missing", { supportingFactIds: ["f2"] }),
      ],
      outline([line("a", ["f1"])]),
    );
    expect(summary.rows.map((row) => row.requirement.requirementId)).toEqual(["missing", "gap", "in"]);
  });
});
