import type { Fact } from "@/api/contracts";
import type { FactPoolEntry } from "./factPool";

/* The pool narrows three ways, as the design draws it: the search field, one knowledge
   file from the chip row, and the pending banner's "only what waits for me". Status and
   tag selects are gone with the filter panel that held them. */
export interface FactFilters {
  pendingOnly: boolean;
  query: string;
  source: string;
}

export const emptyFactFilters: FactFilters = {
  pendingOnly: false,
  query: "",
  source: "all",
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
  return entries.filter(
    ({ fact }) =>
      (query === "" || factSearchText(fact).includes(query)) &&
      (filters.source === "all" || fact.source === filters.source) &&
      (!filters.pendingOnly || fact.status === "pending"),
  );
};
