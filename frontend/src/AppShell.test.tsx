import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { RouterProvider, createMemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import { App } from "./App";

/* A fresh Response per call: a body can only be read once, and the shell issues two
   requests - settings and the Application detail. */
const stubFetch = () =>
  vi.stubGlobal(
    "fetch",
    vi.fn((input: string | URL | Request) =>
      Promise.resolve(
        new Response(
          JSON.stringify(String(input).includes("settings") ? { settings: {} } : { application }),
          { status: 200, headers: { "Content-Type": "application/json" } },
        ),
      ),
    ),
  );

const application = {
  id: "app-1",
  company: "Acme",
  target_role: "Engineer",
  current_status: "saved",
  notes: "",
  source: "manual",
  created_at: "2026-08-24T00:00:00Z",
  updated_at: "2026-08-24T00:00:00Z",
};

/* The shell renders the page below it through an Outlet, so every route here mounts a
   stand-in: what is under test is the header, not the screens.

   A data router rather than `MemoryRouter`, because the shell reads the matched route
   params through `useMatches`, which only a data router provides. */
const renderShell = (path: string) =>
  render(
    <QueryClientProvider
      client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}
    >
      <RouterProvider
        router={createMemoryRouter(
          [
            {
              path: "/",
              element: <App />,
              children: [
                { path: "applications/:applicationId", element: <h1>מועמדות</h1> },
                { path: "applications/:applicationId/draft", element: <h1>טיוטה</h1> },
                { path: "settings", element: <h1>הגדרות</h1> },
              ],
            },
          ],
          { initialEntries: [path] },
        )}
      />
    </QueryClientProvider>,
  );

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("App shell", () => {
  /* The way back from an inner screen. The wordmark goes to the list, one level too far,
     so without this the draft editor and Ready could only be left through the browser's
     back button. */
  it("links the header Application context back to the Application", async () => {
    stubFetch();

    renderShell("/applications/app-1/draft");

    const context = await screen.findByRole("link", { name: /Acme/ });
    expect(context).toHaveAttribute("href", "/applications/app-1");
    expect(context).toHaveTextContent("Engineer");
  });

  /* On the Application screen the same link would point at the page showing it. The
     context is still named, but as text rather than as a way out that goes nowhere. */
  it("states the context without a link on the Application screen itself", async () => {
    stubFetch();

    renderShell("/applications/app-1");

    expect(await screen.findByText("Acme")).toBeInTheDocument();
    expect(screen.queryByRole("link", { name: /Acme/ })).not.toBeInTheDocument();
  });

  /* A screen outside the workflow has no Application to name, and the header says
     nothing rather than whichever one was last loaded. */
  it("shows no Application context off the workflow", async () => {
    stubFetch();

    renderShell("/settings");

    expect(await screen.findByRole("heading", { name: "הגדרות" })).toBeInTheDocument();
    expect(screen.queryByText("Acme")).not.toBeInTheDocument();
  });
});
