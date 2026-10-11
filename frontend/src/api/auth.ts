import { queryOptions } from "@tanstack/react-query";

import { ApiProblem, apiRequest } from "./client";
import type { ChangePasswordRequest, LoginRequest, Me } from "./contracts";

/* Who is signed in. `null` is an answer, not a failure: no valid session is the ordinary
   signed-out state, and the shell routes on it rather than showing an error. */
export const meQueryKey = ["auth", "me"] as const;

export const readMe = async (signal?: AbortSignal): Promise<Me | null> => {
  try {
    return (await apiRequest<Me>("/api/v1/auth/me", { signal })).data;
  } catch (error) {
    if (error instanceof ApiProblem && error.problem.status === 401) return null;
    throw error;
  }
};

export const meQueryOptions = queryOptions({
  queryKey: meQueryKey,
  queryFn: ({ signal }) => readMe(signal),
  /* Read once per page load; a session that ends later says so through a 401. */
  staleTime: Infinity,
});

export const login = async (body: LoginRequest): Promise<Me> =>
  (await apiRequest<Me>("/api/v1/auth/login", { method: "POST", body })).data;

export const logout = async (): Promise<void> => {
  await apiRequest<undefined>("/api/v1/auth/logout", { method: "POST" });
};

export const changePassword = async (body: ChangePasswordRequest): Promise<void> => {
  await apiRequest<undefined>("/api/v1/auth/change-password", { method: "POST", body });
};
