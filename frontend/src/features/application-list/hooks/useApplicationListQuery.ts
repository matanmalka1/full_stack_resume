import { useQuery } from "@tanstack/react-query";
import { useCallback, useEffect, useRef, useState } from "react";
import { useSearchParams } from "react-router-dom";

import { type ApplicationListQuery, applicationListQueryOptions } from "@/api/applications";
import { useDebouncedValue } from "./useDebouncedValue";
import { paramsFromQuery, queryFromParams } from "../model/applicationListParams";

const SEARCH_DEBOUNCE_MS = 300;

interface QueryUpdateOptions {
  replace?: boolean;
  resetOffset?: boolean;
}

/** Owns the board's shareable URL state and its server query.
 *
 * Search text intentionally remains a local input buffer. Only its settled value enters
 * the URL and query key, so typing stays immediate without turning the returned server
 * page into client-owned state.
 */
export const useApplicationListQuery = () => {
  const [params, setParams] = useSearchParams();
  const query = queryFromParams(params);
  const urlSearch = query.search ?? "";
  const [searchInput, setSearchInput] = useState(urlSearch);
  const settledSearch = useDebouncedValue(searchInput, SEARCH_DEBOUNCE_MS);
  const externalSearch = useRef<string | null>(null);
  const previousUrlSearch = useRef(urlSearch);

  const updateQuery = useCallback(
    (next: ApplicationListQuery, { resetOffset = true, replace = true }: QueryUpdateOptions = {}) => {
      setParams(paramsFromQuery(resetOffset ? { ...next, offset: 0 } : next), { replace });
    },
    [setParams],
  );

  useEffect(() => {
    if (urlSearch !== previousUrlSearch.current) {
      previousUrlSearch.current = urlSearch;
      externalSearch.current = urlSearch;
      setSearchInput(urlSearch);
    }
  }, [urlSearch]);

  useEffect(() => {
    if (externalSearch.current !== null) {
      if (settledSearch === externalSearch.current) externalSearch.current = null;
      return;
    }
    if (settledSearch !== (query.search ?? "")) {
      updateQuery({ ...query, search: settledSearch === "" ? undefined : settledSearch });
    }
  }, [query, settledSearch, updateQuery]);

  const listQuery = useQuery(
    applicationListQueryOptions({
      ...query,
      search: settledSearch === "" ? undefined : settledSearch,
    }),
  );

  return {
    listQuery,
    query,
    searchInput,
    setSearchInput,
    updateQuery,
  };
};
