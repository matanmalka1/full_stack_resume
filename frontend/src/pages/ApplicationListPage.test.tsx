import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { ApplicationListItem } from "../api/contracts";
import { ApplicationListPage } from "./ApplicationListPage";
import { actionLabel } from "./applicationLabels";

const item = (overrides: Partial<ApplicationListItem> = {}): ApplicationListItem =>
  ({
    id: "app-1",
    company: "Acme",
    target_role: "Backend Engineer",
    current_status: "saved",
    notes: "",
    source: "manual",
    created_at: "2026-08-24T07:00:00Z",
    updated_at: "2026-08-24T07:00:00Z",
    recruitment_status: "saved",
    preparation_state: "needs_analysis",
    working_draft_state: "none",
    review_reasons: [],
    stale_reasons: [],
    warnings: [],
    active_job_snapshot_id: "snap-1",
    newer_draft_in_progress: false,
    available_actions: ["analyze"],
    blocked_actions: [],
    recommended_action: "analyze",
    ...overrides,
  }) as ApplicationListItem;

const jsonResponse = (body: unknown, status = 200): Response =>
  new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });

const renderPage = () =>
  render(
    <QueryClientProvider
      client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}
    >
      <MemoryRouter initialEntries={["/"]}>
        <Routes>
          <Route element={<ApplicationListPage />} path="/" />
          <Route element={<h1>משרה חדשה</h1>} path="/applications/new" />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("ApplicationListPage", () => {
  /* The reason this screen exists: an Application that was saved has to be reachable
     without its URL, and its row has to say where it stands. */
  it("lists every Application with both of its state axes", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        jsonResponse({
          items: [
            item(),
            item({ id: "app-2", company: "Binat", preparation_state: "ready" }),
          ],
        }),
      ),
    );

    renderPage();

    expect(await screen.findByRole("link", { name: "Acme" })).toHaveAttribute(
      "href",
      "/applications/app-1",
    );
    expect(screen.getByRole("link", { name: "Binat" })).toHaveAttribute(
      "href",
      "/applications/app-2",
    );
    /* Preparation and recruitment are independent axes and the board shows both: one says
       how far the CV has got, the other where the Application stands with the employer. */
    expect(screen.getByText("ממתין לניתוח המשרה")).toBeInTheDocument();
    expect(screen.getByText("קורות החיים מוכנים")).toBeInTheDocument();
    expect(screen.getAllByText("נשמר")).toHaveLength(2);
  });

  /* The board answers "which of these is waiting on me", so the recommended action is a
     column rather than something found by opening each Application in turn. */
  it("names the next action from the projection", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        jsonResponse({
          items: [
            item(),
            item({ id: "app-2", company: "Binat", recommended_action: null }),
            item({
              id: "app-3",
              company: "Cegal",
              preparation_state: "draft_in_progress",
              recommended_action: "update_working_draft",
            }),
          ],
        }),
      ),
    );

    renderPage();

    /* An action with no screen of its own leads to the Application, which is where it is
       taken. */
    expect(await screen.findByRole("link", { name: "ניתוח המשרה" })).toHaveAttribute(
      "href",
      "/applications/app-1",
    );
    expect(screen.getByText("—")).toBeInTheDocument();
    /* One with a screen leads straight to it. The button names the action, so stopping at
       the context screen first asked the reader to find it a second time. */
    expect(screen.getByRole("link", { name: actionLabel("update_working_draft") })).toHaveAttribute(
      "href",
      "/applications/app-3/draft",
    );
  });

  /* The database starts empty, so this is the first screen a new installation shows. */
  it("offers the one action that fills an empty list", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(jsonResponse({ items: [] })));

    renderPage();

    expect(await screen.findByText("עוד לא נוצרה אף מועמדות.")).toBeInTheDocument();
    expect(screen.getAllByRole("link", { name: /משרה חדשה/ })[0]).toHaveAttribute(
      "href",
      "/applications/new",
    );
  });

  it("reports a failed read rather than an empty list", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        jsonResponse(
          {
            type: "about:blank#internal",
            title: "Internal error",
            status: 500,
            code: "INTERNAL",
            detail: "לא ניתן לקרוא את המועמדויות.",
          },
          500,
        ),
      ),
    );

    renderPage();

    expect(await screen.findByRole("alert")).toHaveTextContent("לא ניתן לקרוא את המועמדויות.");
    expect(screen.queryByText("עוד לא נוצרה אף מועמדות.")).not.toBeInTheDocument();
  });
});
