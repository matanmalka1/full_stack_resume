import type { FactStatus } from "@/api/contracts";
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

export const filterFactEntries = (entries: FactPoolEntry[], filters: FactFilters): FactPoolEntry[] => {
  const query = filters.query.trim().toLocaleLowerCase();
  return entries.filter(({ fact }) => {
    const searchable = [fact.meaning, ...Object.values(fact.renderings), fact.provenance, ...fact.tags]
      .join(" ")
      .toLocaleLowerCase();
    return (
      (query === "" || searchable.includes(query)) &&
      (filters.source === "all" || fact.source === filters.source) &&
      (filters.status === "all" || fact.status === filters.status) &&
      (filters.tag === "all" || fact.tags.includes(filters.tag))
    );
  });
};
