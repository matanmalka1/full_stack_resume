import { useQuery } from "@tanstack/react-query";
import type { ReactNode } from "react";
import { Navigate, useLocation } from "react-router-dom";

import { meQueryOptions } from "@/api/auth";
import { routePaths } from "@/navigation/routePaths";
import { QueryState } from "@/ui/QueryState";

/* Every screen but sign-in renders inside this. The server is the check - every route
   it serves refuses without a session - and this only spares the reader a screen that
   would fail: signed out, it goes straight to sign-in and remembers where it was. */
export const SessionGate = ({ children }: { children: ReactNode }) => {
  const location = useLocation();
  const me = useQuery(meQueryOptions);

  if (me.data === null) {
    return <Navigate replace to={routePaths.login(`${location.pathname}${location.search}${location.hash}`)} />;
  }

  return (
    <QueryState
      error={me.error}
      errorTitle="לא ניתן לבדוק את ההתחברות"
      loading={me.data === undefined}
      loadingLabel="טוען…"
    >
      {me.data === undefined ? null : children}
    </QueryState>
  );
};
