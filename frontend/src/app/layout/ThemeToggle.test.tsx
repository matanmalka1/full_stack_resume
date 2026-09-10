import { fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { ThemeToggle } from "./ThemeToggle";

afterEach(() => {
  window.localStorage.clear();
  document.documentElement.removeAttribute("data-theme");
  vi.unstubAllGlobals();
});

describe("ThemeToggle", () => {
  it("follows the system until the user selects and persists a theme", () => {
    vi.stubGlobal("matchMedia", vi.fn(() => ({ matches: true })));
    render(<ThemeToggle />);

    expect(document.documentElement).not.toHaveAttribute("data-theme");
    fireEvent.click(screen.getByRole("button", { name: "מעבר למצב בהיר" }));

    expect(document.documentElement).toHaveAttribute("data-theme", "light");
    expect(window.localStorage.getItem("cv-theme")).toBe("light");
    expect(screen.getByRole("button", { name: "מעבר למצב כהה" })).toBeInTheDocument();
  });

  it("restores an explicit saved theme", () => {
    window.localStorage.setItem("cv-theme", "dark");
    render(<ThemeToggle />);

    expect(document.documentElement).toHaveAttribute("data-theme", "dark");
    expect(screen.getByRole("button", { name: "מעבר למצב בהיר" })).toBeInTheDocument();
  });
});
