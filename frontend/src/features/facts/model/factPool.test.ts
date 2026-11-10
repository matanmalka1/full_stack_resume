import { describe, expect, it } from "vitest";

import type { FactList, FactStatus } from "@/api/contracts";
import { groupFactPool, toFactPool } from "./factPool";

const item = (factId: string, status: FactStatus, recorded: string | null): FactList["items"][number] => ({
  fact: {
    confirmed_at: null,
    effective_dates: null,
    fact_id: factId,
    link_target: null,
    meaning: "Led a B2B sales team",
    renderings: { en: "Led a B2B sales team" },
    replaces: null,
    resume_style: "bullet",
    source: "sales.json",
    status,
    tags: [],
  },
  recorded_status: recorded,
});

describe("the fact pool as the interface reads it", () => {
  it("marks a fact whose status disagrees with its lifecycle log", () => {
    const pool = toFactPool({ items: [item("fact.a", "canonical", "pending")] });

    expect(pool.entries[0]?.outOfSync).toBe(true);
    expect(pool.outOfSyncCount).toBe(1);
  });

  it("leaves a fact alone when the store and the log agree", () => {
    const pool = toFactPool({ items: [item("fact.a", "canonical", "canonical")] });

    expect(pool.entries[0]?.outOfSync).toBe(false);
    expect(pool.outOfSyncCount).toBe(0);
  });

  it("does not require an initial lifecycle event for a canonical source fact", () => {
    const pool = toFactPool({ items: [item("fact.a", "canonical", null)] });

    expect(pool.entries[0]?.outOfSync).toBe(false);
    expect(pool.outOfSyncCount).toBe(0);
  });

  it("counts a non-canonical fact with no lifecycle event as out of sync", () => {
    const pool = toFactPool({ items: [item("fact.a", "pending", null)] });

    expect(pool.entries[0]?.outOfSync).toBe(true);
    expect(pool.outOfSyncCount).toBe(1);
  });

  it("counts only the mismatched facts, and keeps the pool in the order it arrived", () => {
    const pool = toFactPool({
      items: [
        item("fact.a", "canonical", "canonical"),
        item("fact.b", "canonical", "pending"),
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

describe("groupFactPool", () => {
  const entry = (factId: string, source: string, style: string) => ({
    fact: { ...item(factId, "canonical", "canonical").fact, resume_style: style, source },
    outOfSync: false,
  });
  const kinds = [
    { label: "Contact", style: "contact" },
    { label: "Bullets", style: "bullet" },
  ];

  it("groups by file in arrival order, then by kind in the fixed order, unknown kinds last", () => {
    const groups = groupFactPool(
      [
        entry("s.1", "sales.json", "bullet"),
        entry("c.1", "common.json", "contact"),
        entry("s.2", "sales.json", "mystery"),
        entry("s.3", "sales.json", "contact"),
      ],
      kinds,
      (style) => `label:${style}`,
    );

    expect(groups.map((group) => group.source)).toEqual(["sales.json", "common.json"]);
    expect(groups[0]?.kinds.map((kind) => [kind.label, kind.entries.map(({ fact }) => fact.fact_id)])).toEqual([
      ["Contact", ["s.3"]],
      ["Bullets", ["s.1"]],
      ["label:mystery", ["s.2"]],
    ]);
    expect(groups[1]?.kinds.map((kind) => kind.style)).toEqual(["contact"]);
  });
});
