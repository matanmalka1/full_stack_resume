import { describe, expect, it } from "vitest";

import type { DraftClaim } from "@/api/contracts";
import type { DocumentOutline } from "@/api/documents";
import { changeState, regenerationChanges, revertEdit, takeSnapshot } from "./regenerationDiff";

const line = (claim_id: string, text: string, fact_ids: string[] = ["f1"]): DraftClaim => ({
  claim_id,
  claim_type: "reviewed",
  fact_ids,
  style: "bullet",
  text,
});

const outline = (experience: DraftClaim[], skills: DraftClaim[] = []): DocumentOutline => ({
  headline: { ...line("h", "Engineer", []), claim_type: "headline", style: "headline" },
  contacts: [],
  sections: [
    { name: "Experience", claims: experience },
    { name: "Skills", claims: skills },
  ],
});

describe("regeneration diff", () => {
  it("snapshots only the target section and is not affected by later mutation", () => {
    const before = outline([line("a", "old a"), line("b", "old b")], [line("s", "skill")]);
    const snapshot = takeSnapshot(before, "hash-1", { kind: "section", section: "Experience" });
    before.sections[0]!.claims[0]!.text = "mutated";
    expect(snapshot.claims.map((claim) => claim.text)).toEqual(["old a", "old b"]);
  });

  it("snapshots a single claim by id", () => {
    const snapshot = takeSnapshot(outline([line("a", "old a"), line("b", "old b")]), "hash-1", {
      kind: "claim",
      claimId: "b",
    });
    expect(snapshot.claims.map((claim) => claim.claim_id)).toEqual(["b"]);
  });

  it("lists only the lines whose wording changed", () => {
    const snapshot = takeSnapshot(outline([line("a", "old a"), line("b", "same")]), "hash-1", {
      kind: "section",
      section: "Experience",
    });
    const changes = regenerationChanges(snapshot, outline([line("a", "new a", ["f2"]), line("b", "same")]));
    expect(changes).toHaveLength(1);
    expect(changes[0]).toMatchObject({ claimId: "a", before: { text: "old a" }, after: { text: "new a" } });
  });

  it("tracks each change against the draft on screen", () => {
    const snapshot = takeSnapshot(outline([line("a", "old a")]), "hash-1", { kind: "claim", claimId: "a" });
    const [change] = regenerationChanges(snapshot, outline([line("a", "new a")]));
    expect(change).toBeDefined();
    expect(changeState(change!, outline([line("a", "new a")]))).toBe("regenerated");
    expect(changeState(change!, outline([line("a", "old a")]))).toBe("reverted");
    expect(changeState(change!, outline([line("a", "typed since")]))).toBe("edited");
    expect(changeState(change!, outline([]))).toBe("gone");
  });

  it("reverts as an edit carrying the earlier wording and fact links", () => {
    const snapshot = takeSnapshot(outline([line("a", "old a", ["f1"])]), "hash-1", { kind: "claim", claimId: "a" });
    const regenerated = outline([line("a", "new a", ["f2"])]);
    const [change] = regenerationChanges(snapshot, regenerated);
    expect(revertEdit(change!, regenerated)).toEqual({
      claim: { ...line("a", "new a", ["f1"]) },
      text: "old a",
    });
  });

  it("refuses to revert over wording changed since the regeneration", () => {
    const snapshot = takeSnapshot(outline([line("a", "old a")]), "hash-1", { kind: "claim", claimId: "a" });
    const [change] = regenerationChanges(snapshot, outline([line("a", "new a")]));
    expect(revertEdit(change!, outline([line("a", "typed since")]))).toBeNull();
    expect(revertEdit(change!, outline([line("a", "old a")]))).toBeNull();
  });
});
