import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render } from "@testing-library/react";
import type { ReactElement } from "react";
import { MemoryRouter, Route, Routes } from "react-router-dom";

/* The record builders, and the one route harness the screens that read them are rendered
   through. The builders live in `records.ts` so the browser specs share them. */
export * from "./records";

export const json = (value: unknown, status = 200, headers: Record<string, string> = {}) =>
  new Response(JSON.stringify(value), {
    status,
    headers: { "Content-Type": "application/json", ...headers },
  });

export const renderRoute = (entry: string, path: string, element: ReactElement) => {
  const client = new QueryClient({
    defaultOptions: {
      queries: { retry: false, refetchInterval: false, gcTime: 0 },
      mutations: { retry: false },
    },
  });
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={[entry]}>
        <Routes>
          <Route element={element} path={path} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
};
