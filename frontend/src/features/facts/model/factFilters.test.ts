import { describe, expect, it } from "vitest";

import type { FactList } from "@/api/contracts";
import { emptyFactFilters, filterFactEntries } from "./factFilters";
import { toFactPool } from "./factPool";

const entries = toFactPool({
  items: [
    {
      fact: {
        fact_id: "fact.backend",
        meaning: "Built backend services",
        provenance: "candidate notes",
        renderings: { en: "Built APIs", he: "בניית ממשקי API" },
        resume_style: "bullet",
        source: "development.md",
        status: "canonical",
        tags: ["backend", "api"],
      },
      recorded_status: "canonical",
    },
    {
      fact: {
        fact_id: "fact.sales",
        meaning: "Managed enterprise accounts",
        provenance: "candidate notes",
        renderings: { en: "Managed accounts" },
        resume_style: "bullet",
        source: "sales.md",
        status: "pending",
        tags: ["sales"],
      },
      recorded_status: "pending",
    },
  ],
} satisfies FactList).entries;

describe("filterFactEntries", () => {
  it("combines text, status, source, and tag filters", () => {
    expect(filterFactEntries(entries, { ...emptyFactFilters, query: "API" })).toHaveLength(1);
    expect(filterFactEntries(entries, { ...emptyFactFilters, status: "pending" })[0]?.fact.fact_id).toBe("fact.sales");
    expect(filterFactEntries(entries, { ...emptyFactFilters, source: "development.md", tag: "backend" })).toHaveLength(
      1,
    );
    expect(filterFactEntries(entries, { ...emptyFactFilters, source: "sales.md", status: "canonical" })).toEqual([]);
  });
});
