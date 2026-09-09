import { render, screen, within } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it } from "vitest";

import { ApplicationBreadcrumbs } from "./ApplicationBreadcrumbs";

describe("ApplicationBreadcrumbs", () => {
  it("exposes every ancestor as a destination and marks the open page", () => {
    render(
      <MemoryRouter>
        <ApplicationBreadcrumbs
          applicationId="record / עברית"
          company="Google"
          page="draft"
          targetRole="מפתח Full Stack"
        />
      </MemoryRouter>,
    );

    const breadcrumbs = screen.getByRole("navigation", { name: "פירורי לחם" });
    expect(within(breadcrumbs).getByRole("link", { name: "מועמדויות" })).toHaveAttribute("href", "/");
    expect(within(breadcrumbs).getByRole("link", { name: "Google — מפתח Full Stack" })).toHaveAttribute(
      "href",
      "/applications/record%20%2F%20%D7%A2%D7%91%D7%A8%D7%99%D7%AA",
    );
    /* No "הכנת קורות החיים" level between them. It led to a second URL for the screen the
       crumb above already names, so the trail drew two steps that arrived at one place. */
    expect(within(breadcrumbs).queryByText("הכנת קורות החיים")).not.toBeInTheDocument();
    expect(within(breadcrumbs).getByText("עורך טיוטה")).toHaveAttribute("aria-current", "page");
    expect(within(breadcrumbs).queryByRole("link", { name: "עורך טיוטה" })).not.toBeInTheDocument();
  });
});
