import { describe, expect, it } from "vitest";

import type { DraftClaim, WorkingDraft, WorkingDraftFacts } from "../api/contracts";
import { removability } from "./claimRemoval";

const claim = (overrides: Partial<DraftClaim> = {}): DraftClaim => ({
  claim_id: "c-body",
  style: "bullet",
  text: "Led a team of six.",
  claim_type: "canonical",
  fact_ids: ["f-1"],
  pending_reason: null,
  ...overrides,
});

const draft = (claims: DraftClaim[]): WorkingDraft =>
  ({
    id: "wd-1",
    outline: {
      headline: claim({ claim_id: "c-headline", style: "headline", claim_type: "headline" }),
      contacts: [claim({ claim_id: "c-contact", style: "contact", fact_ids: ["f-contact"] })],
      sections: [{ name: "Core Skills", claims }],
    },
    edit_version: 3,
    content_hash: "hash-3",
  }) as unknown as WorkingDraft;

const facts = (rows: Partial<WorkingDraftFacts["facts"][number]>[]): WorkingDraftFacts => ({
  working_draft_id: "wd-1",
  application_id: "app-1",
  selection_plan_id: "sp-1",
  language: "en",
  facts: rows.map((fact) => ({
    fact_id: "f-1",
    text: "Led a team of six.",
    linked_claim_ids: ["c-body"],
    section: "Core Skills",
    outcome: "selected",
    reason: null,
    ...fact,
  })),
});

describe("removability", () => {
  it("sends free text nothing authorized to the patch, the only command that reaches it", () => {
    const line = claim({ claim_type: "pending", fact_ids: [], pending_reason: "no fact" });

    expect(removability(line, draft([line]), facts([]))).toEqual({ route: "patch" });
  });

  it("keeps the headline and the contacts, which the backend refuses as structural", () => {
    const document = draft([claim()]);

    expect(removability(document.outline.headline, document, facts([])).route).toBe("none");
    expect(removability(document.outline.contacts[0]!, document, facts([])).route).toBe("none");
  });

  it("removes an unshared body claim by excluding its facts", () => {
    const line = claim();

    expect(removability(line, draft([line]), facts([{}]))).toEqual({ route: "selection" });
  });

  it("refuses a claim sharing any one fact with a line that stays, and names that line", () => {
    const line = claim({ fact_ids: ["f-1", "f-2"] });
    const other = claim({ claim_id: "c-other", text: "Owned the CRM migration." });
    /* The first fact is this claim's alone; the second is shared. Any one is enough:
       exclusion acts on a fact, not on a line. */
    const result = removability(
      line,
      draft([line, other]),
      facts([{}, { fact_id: "f-2", linked_claim_ids: ["c-body", "c-other"] }]),
    );

    expect(result.route).toBe("none");
    expect(result.reason).toContain("Owned the CRM migration.");
  });

  it("refuses a structural style even when its fact is a plan candidate", () => {
    const line = claim({ claim_id: "c-date", style: "date", text: "2019-2025" });

    expect(removability(line, draft([line]), facts([{ linked_claim_ids: ["c-date"] }])).route).toBe(
      "none",
    );
  });

  it("refuses a fact no selection plan ranked, because there is nothing to exclude it from", () => {
    const line = claim();

    expect(removability(line, draft([line]), facts([{ outcome: null, section: null }])).route).toBe(
      "none",
    );
  });
});
