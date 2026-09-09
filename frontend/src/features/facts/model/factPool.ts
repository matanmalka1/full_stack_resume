import type { Fact, FactList } from "@/api/contracts";

export interface FactPoolEntry {
  fact: Fact;
  /* The fact's own status disagrees with the last status its lifecycle log recorded.
     Canonical source facts need no lifecycle event: the log records mutations, not the
     initial canonical corpus. A non-canonical fact with no event is still out of sync. */
  outOfSync: boolean;
}

export interface FactPool {
  entries: FactPoolEntry[];
  outOfSyncCount: number;
}

export const toFactPool = (data: FactList): FactPool => {
  const entries = data.items.map(({ fact, recorded_status: recordedStatus }) => ({
    fact,
    outOfSync: recordedStatus === null ? fact.status !== "canonical" : recordedStatus !== fact.status,
  }));

  return { entries, outOfSyncCount: entries.filter((entry) => entry.outOfSync).length };
};
