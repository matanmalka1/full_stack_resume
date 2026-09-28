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
  it("states each term of the ranking as a signal, strongest first", () => {
    const ranking = { emphasisScore: 1, gapSubstitute: false, keywordHits: 2, profileScore: 3, requirementRank: 2 };

    expect(factSignals(ranking, [requirement()]).map((signal) => signal.text)).toEqual([
      "ראיה לדרישת חובה",
      "רלוונטית לפרופיל ולדגש (ציון 4)",
      "מכילה 2 מילות מפתח מהמשרה",
    ]);
    expect(
      factSignals({ ...ranking, profileScore: 0, emphasisScore: 0, keywordHits: 0, requirementRank: 0 }, []),
    ).toEqual([{ text: "לא רלוונטית לפרופיל ולדגש הנוכחיים", tone: "negative" }]);
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
