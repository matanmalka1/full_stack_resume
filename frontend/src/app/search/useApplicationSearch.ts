import { useQuery } from "@tanstack/react-query";
import { useDeferredValue, useState } from "react";

import { applicationListQueryOptions } from "@/api/applications";
import type { ApplicationListItem } from "@/api/contracts";

const RESULT_LIMIT = 8;

// Empty field → the board's "needs_attention" preset; otherwise server-side free-text search.
type SearchMode = { kind: "attention" } | { kind: "search"; text: string };

export interface ApplicationSearch {
  search: string;
  setSearch: (value: string) => void;
  mode: SearchMode;
  items: readonly ApplicationListItem[];
  // Shown rows answer an earlier search than the field now holds.
  isStale: boolean;
  isError: boolean;
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

  const mode: SearchMode = deferred === "" ? { kind: "attention" } : { kind: "search", text: deferred };

  return {
    search,
    setSearch,
    mode,
    items: query.data?.items ?? [],
    isStale: query.isPlaceholderData || deferred !== trimmed,
    isError: query.isError,
    isPending: query.isPending,
    retry: () => {
      void query.refetch();
    },
  };
};
