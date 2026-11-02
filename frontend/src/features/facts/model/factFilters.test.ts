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
        source: "development.json",
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
        source: "sales.json",
        status: "pending",
        tags: ["sales"],
      },
      recorded_status: "pending",
    },
  ],
} satisfies FactList).entries;

describe("filterFactEntries", () => {
  it("combines text, source, and pending filters", () => {
    expect(filterFactEntries(entries, { ...emptyFactFilters, query: "API" })).toHaveLength(1);
    expect(filterFactEntries(entries, { ...emptyFactFilters, pendingOnly: true })[0]?.fact.fact_id).toBe("fact.sales");
    expect(
      filterFactEntries(entries, { ...emptyFactFilters, source: "development.json", query: "backend" }),
    ).toHaveLength(1);
    expect(filterFactEntries(entries, { ...emptyFactFilters, source: "development.json", pendingOnly: true })).toEqual(
      [],
    );
  });

  it("finds a fact by its knowledge source, as the global search does", () => {
    expect(
      filterFactEntries(entries, { ...emptyFactFilters, query: "SALES.JSON" }).map(({ fact }) => fact.fact_id),
    ).toEqual(["fact.sales"]);
  });
});
