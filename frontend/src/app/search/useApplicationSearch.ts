import { useQuery } from "@tanstack/react-query";
import { useDeferredValue, useState } from "react";

import { applicationListQueryOptions } from "@/api/applications";
import { factHistoryQueryOptions, factsQueryOptions } from "@/api/facts";
import type { ApplicationListItem, Fact, FactHistory } from "@/api/contracts";

const RESULT_LIMIT = 8;

// Empty field → the board's "needs_attention" preset; otherwise search applications,
// facts and their lifecycle history.
type SearchMode = { kind: "attention" } | { kind: "search"; text: string };

export type GlobalSearchItem =
  | { kind: "application"; id: string; item: ApplicationListItem }
  | { kind: "fact"; id: string; fact: Fact }
  | { kind: "history"; id: string; event: FactHistory["events"][number] };

export interface ApplicationSearch {
  search: string;
  setSearch: (value: string) => void;
  mode: SearchMode;
  items: readonly GlobalSearchItem[];
  applicationMatched: number;
  // Shown rows answer an earlier search than the field now holds.
  isStale: boolean;
  isError: boolean;
  error: unknown;
  isPending: boolean;
  retry: () => void;
}

export const useApplicationSearch = (enabled: boolean): ApplicationSearch => {
  const [search, setSearch] = useState("");
  const trimmed = search.trim();
  const deferred = useDeferredValue(trimmed);

  const query = useQuery({
    ...applicationListQueryOptions(
      deferred === "" ? { preset: "needs_attention", limit: RESULT_LIMIT } : { search: deferred, limit: RESULT_LIMIT },
    ),
    enabled,
  });

  const searchEnabled = enabled && deferred !== "";
  const facts = useQuery({ ...factsQueryOptions(), enabled: searchEnabled });
  const history = useQuery({ ...factHistoryQueryOptions, enabled: searchEnabled });

  const normalized = deferred.toLocaleLowerCase();
  const matchingFacts = (facts.data?.items ?? [])
    .map(({ fact }) => fact)
    .filter((fact) =>
      [fact.meaning, ...Object.values(fact.renderings), fact.provenance, fact.source, ...fact.tags]
        .join(" ")
        .toLocaleLowerCase()
        .includes(normalized),
    );
  const visibleFactIds = new Set((facts.data?.items ?? []).map(({ fact }) => fact.fact_id));
  const matchingHistory = (history.data?.events ?? []).filter(
    (event) =>
      visibleFactIds.has(event.fact_id) &&
      [event.id, event.fact_id, event.event_type, event.source, event.reason, event.from_status, event.to_status]
        .filter((part): part is string => part !== null)
        .join(" ")
        .toLocaleLowerCase()
        .includes(normalized),
  );
  const items: GlobalSearchItem[] = [
    ...(query.data?.items ?? []).map((item) => ({ kind: "application" as const, id: item.id, item })),
    ...matchingFacts.map((fact) => ({ kind: "fact" as const, id: fact.fact_id, fact })),
    ...matchingHistory.map((event) => ({ kind: "history" as const, id: event.id, event })),
  ];
  const isError = query.isError || (searchEnabled && (facts.isError || history.isError));
  const isPending = query.isPending || (searchEnabled && (facts.isPending || history.isPending));

  const mode: SearchMode = deferred === "" ? { kind: "attention" } : { kind: "search", text: deferred };

  return {
    search,
    setSearch,
    mode,
    items,
    applicationMatched: query.data?.matched ?? 0,
    isStale: query.isPlaceholderData || deferred !== trimmed,
    isError,
    error: query.error ?? facts.error ?? history.error,
    isPending,
    retry: () => void Promise.all([query.refetch(), ...(searchEnabled ? [facts.refetch(), history.refetch()] : [])]),
  };
};
