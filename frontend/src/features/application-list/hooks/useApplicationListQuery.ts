import { useQuery } from "@tanstack/react-query";
import { useCallback, useEffect } from "react";
import { useSearchParams } from "react-router-dom";

import { type ApplicationListQuery, applicationListQueryOptions } from "@/api/applications";
import { rememberBoardQuery } from "@/navigation/boardReturn";
import { paramsFromQuery, queryFromParams } from "../model/applicationListParams";

/** Owns the board's shareable URL state and its server query. */
export const useApplicationListQuery = () => {
  const [params, setParams] = useSearchParams();
  const query = queryFromParams(params);

  const updateQuery = useCallback(
    (next: ApplicationListQuery) => {
      setParams(paramsFromQuery(next));
    },
    [setParams],
  );

  /* The board's URL is the board's state, so remembering it here is remembering it once,
     wherever it changed from. The screens that offer a way back read it rather than each
     carrying the parameters themselves. Round-tripped through the board's own parsing, so
     an address arriving with a stale or invented parameter is not handed back later as a
     narrowing the reader chose. */
  const rememberedQuery = paramsFromQuery(query).toString();
  useEffect(() => {
    rememberBoardQuery(rememberedQuery);
  }, [rememberedQuery]);

  const listQuery = useQuery(applicationListQueryOptions(query));

  return { listQuery, query, updateQuery };
};
