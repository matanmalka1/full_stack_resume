import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen } from "@testing-library/react";
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

  /* The board, candidate facts, and settings are not steps: they are durable product
     areas rather than one piece of an Application workflow, and keep the full shell. */
  it.each(["/", "/facts", "/settings", "/nowhere"])("treats %s as outside the wizard", (path) => {
    expect(at(path)).toBe("dashboard");
  });
});

describe("workflow shell", () => {
  it("offers the candidate facts surface as a primary destination outside a wizard", () => {
    render(
      <QueryClientProvider client={new QueryClient()}>
        <MemoryRouter initialEntries={["/facts"]}>
          <AppHeader />
        </MemoryRouter>
      </QueryClientProvider>,
    );

    expect(screen.getByRole("link", { name: "מאגר העובדות" })).toHaveAttribute("href", "/facts");
    expect(screen.getByRole("link", { name: "מאגר העובדות" })).toHaveAttribute("aria-current", "page");
  });

  it("hides global destinations but keeps the command palette shortcut in a wizard step", () => {
    render(
      <QueryClientProvider client={new QueryClient()}>
        <MemoryRouter initialEntries={["/applications/app-1/draft"]}>
          <AppHeader />
        </MemoryRouter>
      </QueryClientProvider>,
    );

    expect(screen.queryByRole("button", { name: "מעבר מהיר למועמדות (Cmd+K)" })).not.toBeInTheDocument();
    expect(screen.queryByRole("link", { name: "קליטת משרה חדשה" })).not.toBeInTheDocument();

    fireEvent.keyDown(window, { key: "k", metaKey: true });
    expect(screen.getByRole("dialog", { name: "מעבר מהיר למועמדות" })).toBeInTheDocument();
  });
});
