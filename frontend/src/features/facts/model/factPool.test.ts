import { describe, expect, it } from "vitest";

import type { FactList, FactStatus } from "@/api/contracts";
import { toFactPool } from "./factPool";

const item = (factId: string, status: FactStatus, recorded: string | null): FactList["items"][number] => ({
  fact: {
    confirmed_at: null,
    effective_dates: null,
    fact_id: factId,
    link_target: null,
    meaning: "Led a B2B sales team",
    provenance: "Confirmed by candidate",
    renderings: { en: "Led a B2B sales team" },
    replaces: null,
    resume_style: "bullet",
    source: "sales.md",
    status,
    tags: [],
  },
  recorded_status: recorded,
});

describe("the fact pool as the interface reads it", () => {
  it("marks a fact whose status disagrees with its lifecycle log", () => {
    const pool = toFactPool({ items: [item("fact.a", "canonical", "confirmed")] });

    expect(pool.entries[0]?.outOfSync).toBe(true);
    expect(pool.outOfSyncCount).toBe(1);
  });

  it("leaves a fact alone when the store and the log agree", () => {
    const pool = toFactPool({ items: [item("fact.a", "canonical", "canonical")] });

    expect(pool.entries[0]?.outOfSync).toBe(false);
    expect(pool.outOfSyncCount).toBe(0);
  });

  /* A fact the log never recorded is what a lost write leaves behind, so it is a
     mismatch rather than a fact with nothing to compare against. */
  it("counts a fact the log never recorded as out of sync", () => {
    const pool = toFactPool({ items: [item("fact.a", "canonical", null)] });

    expect(pool.entries[0]?.outOfSync).toBe(true);
    expect(pool.outOfSyncCount).toBe(1);
  });

  it("counts only the mismatched facts, and keeps the pool in the order it arrived", () => {
    const pool = toFactPool({
      items: [
        item("fact.a", "canonical", "canonical"),
        item("fact.b", "confirmed", "pending"),
        item("fact.c", "pending", null),
      ],
    });

    expect(pool.entries.map((entry) => entry.fact.fact_id)).toEqual(["fact.a", "fact.b", "fact.c"]);
    expect(pool.outOfSyncCount).toBe(2);
  });

  it("reports an empty store as a pool with nothing to reconcile", () => {
    expect(toFactPool({ items: [] })).toEqual({ entries: [], outOfSyncCount: 0 });
  });
});
