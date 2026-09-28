import { describe, expect, it } from "vitest";

import type { Requirement } from "@/api/analyses";
import type { DocumentCandidate } from "@/api/contracts";
import { decisionSource, factSignals, includedFactIds, selectionChanges } from "./selectionManifest";

const candidate = (overrides: Partial<DocumentCandidate> = {}): DocumentCandidate => ({
  fact_id: "fact.a",
  outcome: "selected",
  reason: null,
  section: "Work Experience",
  text: "Led a B2B sales team",
  user_selectable: true,
  ...overrides,
});

const requirement = (overrides: Partial<Requirement> = {}): Requirement => ({
  requirementId: "requirement-1",
  text: "B2B sales",
  importance: "mandatory",
  coverage: "matched",
  shortfallSeverity: null,
  shortfallReason: null,
  supportingFactIds: ["fact.a"],
  boundaryFactIds: [],
  ...overrides,
});

describe("the selection the fact list explains itself from", () => {
  it("states the requirements a fact is evidence for, mandatory first", () => {
    const preferred = requirement({ requirementId: "requirement-2", importance: "preferred" });

    expect(factSignals([requirement(), preferred]).map((signal) => signal.text)).toEqual([
      "ראיה לדרישת חובה",
      "ראיה לדרישה נוספת במשרה",
    ]);
    expect(factSignals([])).toEqual([]);
  });

  it("names who placed a fact: the engine, an explicit mark, or the document structure", () => {
    expect(decisionSource(candidate(), [], [])).toBe("engine");
    expect(decisionSource(candidate(), ["fact.a"], [])).toBe("pinned");
    expect(decisionSource(candidate(), [], ["fact.a"])).toBe("excluded");
    expect(decisionSource(candidate({ user_selectable: false }), [], ["fact.a"])).toBe("locked");
  });

  it("reports what a new selection added and removed against the facts included before it", () => {
    const candidates = [
      candidate({ fact_id: "kept" }),
      candidate({ fact_id: "added", outcome: "pinned" }),
      candidate({ fact_id: "removed", outcome: "omitted", reason: "excluded_by_user" }),
      candidate({ fact_id: "still.out", outcome: "omitted", reason: "below_section_budget" }),
    ];

    const changes = selectionChanges(["kept", "removed"], candidates, ["added"], ["removed"]);

    expect(changes.map((change) => [change.candidate.fact_id, change.direction])).toEqual([
      ["added", "added"],
      ["removed", "removed"],
    ]);
    expect(includedFactIds(candidates, ["added"], ["removed"])).toEqual(["kept", "added"]);
  });
});
