import { describe, expect, it } from "vitest";

import { defaultFactSource, emptyFactForm, factFieldRules, parseFactTags } from "./factForm";

describe("where a new fact is filed", () => {
  it("files it under the active Profile's own track", () => {
    expect(defaultFactSource("development")).toBe("development.md");
    expect(defaultFactSource("field-sales")).toBe("sales.md");
  });

  /* A guess, not a decision: the person can still pick any source, so the absence of a
     Profile picks a starting point rather than refusing to open the form. */
  it("still offers a starting source with no active Profile", () => {
    expect(defaultFactSource(null)).toBe("sales.md");
  });
});

describe("the fact form's starting state", () => {
  /* Captured from a draft claim, the claim's own text is the meaning and is carried in
     verbatim - this flow never rewords it. */
  it("carries a supplied meaning through untouched and leaves the rest empty", () => {
    expect(emptyFactForm("development", "Delivered 30% growth.")).toEqual({
      english: "",
      hebrew: "",
      meaning: "Delivered 30% growth.",
      provenance: "",
      source: "development.md",
      style: "bullet",
      tags: "",
    });
  });

  it("starts blank when no meaning is supplied", () => {
    expect(emptyFactForm(null).meaning).toBe("");
  });
});

describe("reading the tags a person typed", () => {
  it("splits on commas and drops the spacing around each tag", () => {
    expect(parseFactTags("sales, crm ,  b2b")).toEqual(["sales", "crm", "b2b"]);
  });

  it("drops empty entries rather than storing a blank tag", () => {
    expect(parseFactTags("sales,,crm,")).toEqual(["sales", "crm"]);
    expect(parseFactTags(" , ")).toEqual([]);
    expect(parseFactTags("")).toEqual([]);
  });
});

describe("what the form refuses before the round trip", () => {
  /* These spare the request and name the missing field where the person is looking. The
     server's own validation stays authoritative; nothing here replaces it. */
  it("refuses a field holding only whitespace, and names it in Hebrew", () => {
    expect(factFieldRules.meaning.validate("   ")).toBe("יש להזין משמעות.");
    expect(factFieldRules.english.validate("")).toBe("יש להזין ניסוח באנגלית.");
    expect(factFieldRules.provenance.validate(" \n ")).toBe("יש להזין מקור ואימות.");
  });

  it("requires at least one real tag, not just punctuation", () => {
    expect(factFieldRules.tags.validate(" , , ")).toBe("יש להזין תגית אחת לפחות.");
    expect(factFieldRules.tags.validate("sales")).toBe(true);
  });

  it("accepts a filled field", () => {
    expect(factFieldRules.meaning.validate("Led a B2B sales team")).toBe(true);
    expect(factFieldRules.provenance.validate("Confirmed by candidate")).toBe(true);
  });
});
