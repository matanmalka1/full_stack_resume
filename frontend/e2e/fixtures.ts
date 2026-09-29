import { test as base, expect, type Route } from "@playwright/test";

import { settings } from "../src/test/records";

/* The mocked UI suite's `test`. Every spec under `e2e/` except `integration/` imports it
   from here; a lint rule refuses the direct import, so a new spec is covered without being
   registered anywhere.

   Every `/api/` request the browser context makes is answered from the scenario's stub
   table or not at all. A request with no stub is aborted - it never reaches the preview
   server or an API that happens to be running on the developer's machine - and the test
   fails at teardown naming it. Answering it with an error instead would not do: the
   screen shows the error as designed and the test passes over a state it never set up.

   A stub is keyed by method, path, and the exact query. Parameters are compared sorted, so
   their order in the URL does not matter, but every one of them does: a stub declared
   without a query answers only the request without one.

   `page.route` and `context.route` refuse inside this suite. A route of its own would
   answer ahead of the table and skip the method and query match. */

export type Answer = (route: Route) => Promise<void>;

export const json =
  (body: unknown, { status = 200, headers = {} }: { status?: number; headers?: Record<string, string> } = {}): Answer =>
  (route) =>
    route.fulfill({ status, contentType: "application/json", headers, json: body });

export interface Api {
  /* `request` is `"<METHOD> <path>[?query]"`. A later stub for the same request replaces
     the earlier one, so a test can override a `beforeEach` default. */
  stub: (request: string, answer: Answer) => void;
}

const requestKey = (method: string, url: URL): string => {
  const params = new URLSearchParams(url.search);
  params.sort();
  const query = params.toString();
  return `${method.toUpperCase()} ${url.pathname}${query === "" ? "" : `?${query}`}`;
};

const declaredKey = (request: string): string => {
  const [method = "", target = ""] = request.trim().split(/\s+/, 2);
  return requestKey(method, new URL(target, "http://stub.invalid"));
};

const refuseRoute = async (): Promise<never> => {
  throw new Error("Stub API requests with the api fixture (api.stub), not page.route or context.route.");
};

export const test = base.extend<{ api: Api }>({
  page: async ({ page }, use) => {
    page.route = refuseRoute;
    await use(page);
  },
  api: [
    async ({ context }, use) => {
      const table = new Map<string, Answer>();
      const unstubbed: string[] = [];
      const api: Api = {
        stub: (request, answer) => {
          table.set(declaredKey(request), answer);
        },
      };

      /* Every screen sits in the shell, and the shell reads Settings. One deliberate default
         rather than a copy per spec; a scenario about Settings replaces it. */
      api.stub("GET /api/v1/settings", json(settings()));

      await context.route(
        (url) => url.pathname.startsWith("/api/"),
        async (route) => {
          const request = route.request();
          const key = requestKey(request.method(), new URL(request.url()));
          const answer = table.get(key);
          if (answer === undefined) {
            unstubbed.push(key);
            await route.abort("blockedbyclient");
            return;
          }
          await answer(route);
        },
      );
      context.route = refuseRoute;

      await use(api);

      if (unstubbed.length > 0) {
        throw new Error(`Unstubbed API request:\n${[...new Set(unstubbed)].join("\n")}`);
      }
    },
    { auto: true },
  ],
});

export { expect };
