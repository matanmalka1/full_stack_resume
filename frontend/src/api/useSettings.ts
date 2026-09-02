import { useQuery } from "@tanstack/react-query";

import { settingsQueryOptions } from "./settings";
import type { Settings } from "./contracts";

/* App owns the live settings read; every other screen consumes that cache rather than
   opening a request of its own, so this stays `enabled: false` on purpose. What this
   wraps is the one thing three call sites used to reimplement locally: telling "AI is
   unavailable" apart from "the read App is doing hasn't come back yet". A query that
   never runs never fails, so there is no error to report here either. */
export const useSettings = (): { settings: Settings | undefined; isPending: boolean } => {
  const query = useQuery({ ...settingsQueryOptions, enabled: false });

  return { settings: query.data?.settings, isPending: query.isPending };
};
