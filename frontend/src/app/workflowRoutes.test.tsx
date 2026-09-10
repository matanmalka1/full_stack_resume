import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { describe, expect, it } from "vitest";

import { useInWorkflow } from "./workflowRoutes";
import { AppHeader } from "./layout/AppHeader";

const Probe = () => <span>{useInWorkflow() ? "wizard" : "dashboard"}</span>;

const at = (path: string) => {
  render(
    <MemoryRouter initialEntries={[path]}>
      <Routes>
        <Route element={<Probe />} path="*" />
      </Routes>
    </MemoryRouter>,
  );

  return screen.getByText(/wizard|dashboard/).textContent;
};

describe("useInWorkflow", () => {
  /* The workflow routes `router.tsx` declares. A step that stops matching here is a step that
     silently gets the board's chrome back. */
  it.each([
    "/applications/new",
    "/applications/app-1",
    "/applications/app-1/resume",
    "/applications/app-1/draft",
    "/revisions/rev-1",
  ])("treats %s as a wizard step", (path) => {
    expect(at(path)).toBe("wizard");
  });

  /* The board and settings are not steps: they are where a reader goes to choose work
     rather than to do one piece of it, and they keep the full shell. */
  it.each(["/", "/settings", "/nowhere"])("treats %s as outside the wizard", (path) => {
    expect(at(path)).toBe("dashboard");
  });
});

describe("workflow shell", () => {
  it("removes global destinations while the reader is completing a wizard step", () => {
    render(
      <QueryClientProvider client={new QueryClient()}>
        <MemoryRouter initialEntries={["/applications/app-1/draft"]}>
          <AppHeader />
        </MemoryRouter>
      </QueryClientProvider>,
    );

    expect(screen.queryByRole("button", { name: "מעבר מהיר למועמדות (Cmd+K)" })).not.toBeInTheDocument();
    expect(screen.queryByRole("link", { name: "קליטת משרה חדשה" })).not.toBeInTheDocument();
  });
});
