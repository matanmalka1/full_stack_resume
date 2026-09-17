import { render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { AppErrorBoundary } from "./AppErrorBoundary";

const BrokenChild = () => {
  throw new Error("provider failed");
};

describe("AppErrorBoundary", () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("renders its children while the application is healthy", () => {
    render(
      <AppErrorBoundary>
        <p>application content</p>
      </AppErrorBoundary>,
    );

    expect(screen.getByText("application content")).toBeInTheDocument();
  });

  it("shows a recovery screen and reports an uncaught render failure", () => {
    const consoleError = vi.spyOn(console, "error").mockImplementation(() => undefined);

    render(
      <AppErrorBoundary homePath="/home">
        <BrokenChild />
      </AppErrorBoundary>,
    );

    expect(screen.getByRole("heading", { name: "אירעה שגיאה בלתי צפויה" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "טעינה מחדש" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "חזרה לדף הבית" })).toHaveAttribute("href", "/home");
    expect(screen.getByText(/Error: provider failed/)).toBeInTheDocument();
    expect(consoleError).toHaveBeenCalledWith(
      "app_error_boundary",
      expect.objectContaining({ message: "provider failed", name: "Error" }),
    );
  });
});
