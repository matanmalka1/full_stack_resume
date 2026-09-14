import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import { applicationDetailQueryKey } from "@/api/applications";
import { queryClient as appQueryClient } from "@/app/queryClient";
import { detail, json, operation } from "@/test/fixtures";
import { ApplicationResumePage } from "./ApplicationResumePage";

afterEach(() => {
  vi.unstubAllGlobals();
});

const renderResume = (
  projection = detail(),
  fetchMock: (input: RequestInfo | URL, init?: RequestInit) => Promise<Response> = vi.fn<
    (input: RequestInfo | URL, init?: RequestInit) => Promise<Response>
  >(() => Promise.resolve(json(projection))),
  cached?: ReturnType<typeof detail>,
) => {
  vi.stubGlobal("fetch", fetchMock);
  const client = new QueryClient({
    defaultOptions: {
      queries: { retry: 1, retryDelay: 0 },
      mutations: appQueryClient.getDefaultOptions().mutations,
    },
  });
  if (cached !== undefined) client.setQueryData(applicationDetailQueryKey("app-1"), cached);
  render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={["/applications/app-1/resume"]}>
        <Routes>
          <Route element={<ApplicationResumePage />} path="/applications/:applicationId/resume" />
          <Route element={<h1>ניתוח</h1>} path="/applications/:applicationId" />
          <Route element={<h1>טיוטה</h1>} path="/applications/:applicationId/draft" />
          <Route element={<h1>מוכן</h1>} path="/revisions/revision-1" />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
  return fetchMock;
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
  it.each(["needs_analysis", "needs_review", "ready_to_draft"] as const)(
    "recovers %s without navigation state",
    async (preparation_state) => {
      renderResume(detail({ preparation_state, recommended_action: null }));
      expect(await screen.findByRole("heading", { name: "ניתוח" })).toBeInTheDocument();
    },
  );

  it.each(["network", "500"])(
    "shows final %s failure after the automatic retry and recovers with one explicit read",
    async (failure) => {
      const fetchMock = vi
        .fn<(input: RequestInfo | URL, init?: RequestInit) => Promise<Response>>()
        .mockImplementationOnce(() =>
          failure === "network" ? Promise.reject(new TypeError("offline")) : Promise.resolve(json({}, 500)),
        )
        .mockImplementationOnce(() =>
          failure === "network" ? Promise.reject(new TypeError("offline")) : Promise.resolve(json({}, 500)),
        )
        .mockImplementationOnce(() => Promise.resolve(json(detail())));
      renderResume(detail(), fetchMock);
      expect(screen.getByRole("status")).toHaveTextContent("בודק מהו השלב הפעיל");
      expect(await screen.findByRole("alert")).toBeInTheDocument();
      expect(fetchMock).toHaveBeenCalledTimes(2);
      expect(screen.queryByText("בודק מהו השלב הפעיל…")).not.toBeInTheDocument();
      fireEvent.click(screen.getByRole("button", { name: "ניסיון חוזר" }));
      expect(await screen.findByRole("heading", { name: "טיוטה" })).toBeInTheDocument();
      expect(fetchMock).toHaveBeenCalledTimes(3);
      expect(
        fetchMock.mock.calls.every(
          ([input, init]) => String(input) === "/api/v1/applications/app-1" && init?.method !== "POST",
        ),
      ).toBe(true);
    },
  );

  it("keeps 404 as not found without a workflow retry or redirect", async () => {
    renderResume(
      detail(),
      vi.fn(() =>
        Promise.resolve(
          json({ type: "about:blank", title: "Not found", status: 404, code: "NOT_FOUND", detail: "Missing" }, 404),
        ),
      ),
    );
    expect(await screen.findByRole("heading", { name: "העמוד לא נמצא" })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "ניסיון חוזר" })).not.toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: "טיוטה" })).not.toBeInTheDocument();
  });

  it("waits for the server instead of redirecting from a stale cached stage", async () => {
    let resolve: (response: Response) => void = () => {};
    const fetchMock = vi.fn(
      () =>
        new Promise<Response>((settle) => {
          resolve = settle;
        }),
    );
    renderResume(
      detail(),
      fetchMock,
      detail({ preparation_state: "ready", latest_ready_revision_id: "revision-1", recommended_action: null }),
    );
    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(1));
    expect(screen.queryByRole("heading", { name: "מוכן" })).not.toBeInTheDocument();
    await act(async () =>
      resolve(json(detail({ preparation_state: "needs_review", recommended_action: "apply_analysis_decisions" }))),
    );
    expect(await screen.findByRole("heading", { name: "ניתוח" })).toBeInTheDocument();
  });

  it.each([
    ["analyze_job", "ניתוח"],
    ["propose_selection_plan", "ניתוח"],
    ["create_draft", "ניתוח"],
    ["regenerate_section", "טיוטה"],
    ["regenerate_claim", "טיוטה"],
    ["render_revision", "טיוטה"],
  ] as const)("restores active %s work ahead of a Ready milestone", async (operation_type, heading) => {
    renderResume(
      detail({
        preparation_state: "ready",
        latest_ready_revision_id: "revision-1",
        recommended_action: null,
        active_operation: { ...operation(), operation_type, status: "running", is_terminal: false },
      }),
    );
    expect(await screen.findByRole("heading", { name: heading })).toBeInTheDocument();
  });
});
