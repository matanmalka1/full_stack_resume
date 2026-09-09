import { render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { describe, expect, it } from "vitest";

import { useInWorkflow } from "./workflowRoutes";

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
  /* The four steps `router.tsx` declares. A step that stops matching here is a step that
     silently gets the board's chrome back. */
  it.each(["/applications/new", "/applications/app-1", "/applications/app-1/draft", "/revisions/rev-1"])(
    "treats %s as a wizard step",
    (path) => {
      expect(at(path)).toBe("wizard");
    },
  );

  /* The board and settings are not steps: they are where a reader goes to choose work
     rather than to do one piece of it, and they keep the full shell. */
  it.each(["/", "/settings", "/nowhere"])("treats %s as outside the wizard", (path) => {
    expect(at(path)).toBe("dashboard");
  });
});
