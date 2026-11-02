import { describe, expect, it } from "vitest";

import type { DraftClaim } from "@/api/contracts";
import { cvDocument } from "@/test/fixtures";
import { unsupportedClaims } from "./draftOverview";
import type { EditableDocument } from "./drafts.types";

const line = (claim_id: string, claim_type: DraftClaim["claim_type"], fact_ids: string[] = []): DraftClaim => ({
  claim_id,
  claim_type,
  fact_ids,
  style: "bullet",
  text: claim_id,
});

const documentWith = (claims: DraftClaim[], headline = line("h", "headline")) =>
  cvDocument({
    outline: { headline, contacts: [], sections: [{ name: "Experience", claims }] },
  }) as EditableDocument;

describe("unsupportedClaims", () => {
  it("lists only the lines nothing authorizes", () => {
    const claims = unsupportedClaims(
      documentWith([
        line("a", "canonical", ["f"]),
        line("b", "derived", ["f"]),
        line("c", "composite", ["f", "g"]),
        line("d", "reviewed", ["f"]),
        line("e", "pending"),
      ]),
    );

    expect(claims.map((claim) => claim.claim_id)).toEqual(["e"]);
  });

  it("lists an unsupported headline too, in reading order", () => {
    const claims = unsupportedClaims(documentWith([line("a", "pending")], line("h", "pending")));

    expect(claims.map((claim) => claim.claim_id)).toEqual(["h", "a"]);
  });
});
