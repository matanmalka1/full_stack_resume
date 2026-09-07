import { useQuery } from "@tanstack/react-query";

import { factDetailQueryOptions, factsQueryOptions } from "@/api/facts";
import { toFactPool } from "../model/factPool";

/* The whole fact pool, with the store-versus-log comparison applied once in `select`
   rather than re-derived by each screen that shows it. */
export const useFactPool = () => useQuery({ ...factsQueryOptions(), select: toFactPool });

export const useFactDetail = (factId: string | null) =>
  useQuery({ ...factDetailQueryOptions(factId ?? ""), enabled: factId !== null });
