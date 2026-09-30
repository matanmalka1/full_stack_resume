import { describe, expect, it } from "vitest";

import type { Requirement } from "@/api/analyses";
import { coverageCounts, requirementGroups, requirementsByFact } from "./requirementGroups";

const requirement = (id: string, overrides: Partial<Requirement> = {}): Requirement => ({
  requirementId: id,
  text: id,
  importance: "mandatory",
  coverage: "matched",
  shortfallSeverity: null,
  shortfallReason: null,
  rationale: null,
  supportingFactIds: [],
  boundaryFactIds: [],
  ...overrides,
});

const requirements = [
  requirement("preferred.matched", { importance: "preferred" }),
  requirement("mandatory.matched"),
  requirement("mandatory.partial", { coverage: "partial" }),
  requirement("unknown.unsupported", { importance: "unknown", coverage: "unsupported" }),
  requirement("mandatory.unsupported", { coverage: "unsupported", supportingFactIds: ["fact.a"] }),
];

describe("requirements as the analysis panel groups them", () => {
  it("groups by importance, mandatory first, with the requirements needing attention leading", () => {
    const groups = requirementGroups(requirements);

    expect(groups.map((group) => group.importance)).toEqual(["mandatory", "preferred", "unknown"]);
    expect(groups[0]?.requirements.map((item) => item.requirementId)).toEqual([
      "mandatory.unsupported",
      "mandatory.partial",
      "mandatory.matched",
    ]);
    expect(groups[0]).toMatchObject({ matched: 1, total: 3 });
  });

  it("narrows the rows but keeps each group's counts whole", () => {
    const [mandatory, preferred] = requirementGroups(requirements, "attention");

    expect(mandatory?.requirements.map((item) => item.requirementId)).toEqual([
      "mandatory.unsupported",
      "mandatory.partial",
    ]);
    expect(mandatory).toMatchObject({ matched: 1, total: 3 });
    expect(preferred?.requirements).toEqual([]);
  });

  it("counts coverage and indexes which requirements each fact supports", () => {
    expect(coverageCounts(requirements)).toEqual({ matched: 2, partial: 1, unsupported: 2, unknown: 0 });
    expect(
      requirementsByFact([
        requirement("one", { supportingFactIds: ["fact.a"], boundaryFactIds: ["fact.b"] }),
        requirement("two", { supportingFactIds: ["fact.a"] }),
      ]).get("fact.a"),
    ).toHaveLength(2);
    expect(requirementsByFact(requirements).has("fact.b")).toBe(false);
  });
});
