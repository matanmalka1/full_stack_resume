import type { Fact, FactList } from "@/api/contracts";

export interface FactPoolEntry {
  fact: Fact;
  /* The fact's own status disagrees with the last status its lifecycle log recorded.
     Canonical source facts need no lifecycle event: the log records mutations, not the
     initial canonical corpus. A non-canonical fact with no event is still out of sync. */
  outOfSync: boolean;
}

interface FactPool {
  entries: FactPoolEntry[];
  outOfSyncCount: number;
}

export interface FactKindGroup {
  entries: FactPoolEntry[];
  label: string;
  style: string;
}

export interface FactSourceGroup {
  entries: FactPoolEntry[];
  kinds: FactKindGroup[];
  source: string;
}

/* The pool's two levels of order: the knowledge file a fact lives in - the axis the chips
   narrow by - and, inside it, the fact's kind in the fixed order `factKindSections`
   gives. Files keep the order the pool arrived in, and so do the facts inside a kind: the
   store's own order is what the store and the integrity report show. A kind the frontend
   does not know yet closes the file under its own name rather than vanishing. */
export const groupFactPool = (
  entries: FactPoolEntry[],
  kinds: { label: string; style: string }[],
  kindLabel: (style: string) => string,
): FactSourceGroup[] => {
  const bySource = new Map<string, FactPoolEntry[]>();
  for (const entry of entries) {
    const existing = bySource.get(entry.fact.source);
    if (existing === undefined) bySource.set(entry.fact.source, [entry]);
    else existing.push(entry);
  }

  const known = new Set(kinds.map(({ style }) => style));
  return [...bySource].map(([source, grouped]) => {
    const unknownStyles = [...new Set(grouped.map(({ fact }) => fact.resume_style))].filter(
      (style) => !known.has(style),
    );
    const order = [...kinds, ...unknownStyles.map((style) => ({ label: kindLabel(style), style }))];
    return {
      entries: grouped,
      kinds: order
        .map(({ label, style }) => ({
          entries: grouped.filter(({ fact }) => fact.resume_style === style),
          label,
          style,
        }))
        .filter((kind) => kind.entries.length > 0),
      source,
    };
  });
};

export const toFactPool = (data: FactList): FactPool => {
  const entries = data.items.map(({ fact, recorded_status: recordedStatus }) => ({
    fact,
    outOfSync: recordedStatus === null ? fact.status !== "canonical" : recordedStatus !== fact.status,
  }));

  return { entries, outOfSyncCount: entries.filter((entry) => entry.outOfSync).length };
};
