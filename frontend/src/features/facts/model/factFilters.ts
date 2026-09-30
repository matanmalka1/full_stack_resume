import type { Fact, FactStatus } from "@/api/contracts";
import type { FactPoolEntry } from "./factPool";

export interface FactFilters {
  query: string;
  source: string;
  status: FactStatus | "all";
  tag: string;
}

export const emptyFactFilters: FactFilters = {
  query: "",
  source: "all",
  status: "all",
  tag: "all",
};

/* Everything a fact is found by, as one lowercased string: its meaning, every rendering,
   provenance, knowledge source and tags. The facts screen and the global search palette
   both search with this, so the same words find the same facts in either. */
export const factSearchText = (fact: Fact): string =>
  [fact.meaning, ...Object.values(fact.renderings), fact.provenance, fact.source, ...fact.tags]
    .join(" ")
    .toLocaleLowerCase();

export const filterFactEntries = (entries: FactPoolEntry[], filters: FactFilters): FactPoolEntry[] => {
  const query = filters.query.trim().toLocaleLowerCase();
  return entries.filter(({ fact }) => {
    return (
      (query === "" || factSearchText(fact).includes(query)) &&
      (filters.source === "all" || fact.source === filters.source) &&
      (filters.status === "all" || fact.status === filters.status) &&
      (filters.tag === "all" || fact.tags.includes(filters.tag))
    );
  });
};
