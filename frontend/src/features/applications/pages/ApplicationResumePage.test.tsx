import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import { detail, json } from "@/test/fixtures";
import { ApplicationResumePage } from "./ApplicationResumePage";

afterEach(() => {
  vi.unstubAllGlobals();
});

const renderResume = (projection = detail()) => {
  vi.stubGlobal(
    "fetch",
    vi.fn(() => Promise.resolve(json(projection))),
  );

  render(
    <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
      <MemoryRouter initialEntries={["/applications/app-1/resume"]}>
        <Routes>
          <Route element={<ApplicationResumePage />} path="/applications/:applicationId/resume" />
          <Route element={<h1>ניתוח</h1>} path="/applications/:applicationId" />
          <Route element={<h1>טיוטה</h1>} path="/applications/:applicationId/draft" />
          <Route element={<h1>מוכן</h1>} path="/revisions/:revisionId" />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
};

describe("ApplicationResumePage", () => {
  it("opens the draft screen selected by the current server projection", async () => {
    renderResume(detail({ preparation_state: "ready_for_approval", recommended_action: "approve" }));

    expect(await screen.findByRole("heading", { name: "טיוטה" })).toBeInTheDocument();
  });

  it("opens the exact ready revision", async () => {
    renderResume(
      detail({
        latest_ready_revision_id: "revision-1",
        preparation_state: "ready",
        recommended_action: null,
      }),
    );

    expect(await screen.findByRole("heading", { name: "מוכן" })).toBeInTheDocument();
  });
});
