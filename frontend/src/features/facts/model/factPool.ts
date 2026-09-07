import type { Fact, FactList } from "@/api/contracts";

export interface FactPoolEntry {
  fact: Fact;
  /* The fact's own status disagrees with the last status its lifecycle log recorded.
     That gap is evidence of a write that did not finish, so the fact must be reconciled
     before anything uses it again. A fact the log never recorded at all counts as out of
     sync too: an unrecorded fact is exactly what a lost write leaves behind. */
  outOfSync: boolean;
}

export interface FactPool {
  entries: FactPoolEntry[];
  outOfSyncCount: number;
}

export const toFactPool = (data: FactList): FactPool => {
  const entries = data.items.map(({ fact, recorded_status: recordedStatus }) => ({
    fact,
    outOfSync: recordedStatus !== fact.status,
  }));

  return { entries, outOfSyncCount: entries.filter((entry) => entry.outOfSync).length };
};
