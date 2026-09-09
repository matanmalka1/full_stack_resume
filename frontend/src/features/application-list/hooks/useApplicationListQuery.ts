import { useQuery } from "@tanstack/react-query";
import { useCallback, useEffect, useRef, useState } from "react";
import { useSearchParams } from "react-router-dom";

import { type ApplicationListQuery, applicationListQueryOptions } from "@/api/applications";
import { rememberBoardQuery } from "@/app/boardReturn";
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

  /* The board's URL is the board's state, so remembering it here is remembering it once,
     wherever it changed from - a filter, the search box settling, a page step, or a link
     that arrived already filtered. The screens that offer a way back read it rather than
     each carrying the parameters themselves.

     Round-tripped through the board's own parsing rather than stored as the raw location:
     an address typed or shared with a stale or invented parameter would otherwise be
     handed back later as if the board had asked for it. `updateQuery` writes the same
     canonical form, so only the landing URL can differ. */
  const rememberedQuery = paramsFromQuery(query).toString();
  useEffect(() => {
    rememberBoardQuery(rememberedQuery);
  }, [rememberedQuery]);

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
