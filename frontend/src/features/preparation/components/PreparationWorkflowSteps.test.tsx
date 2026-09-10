import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it } from "vitest";

import { detail } from "@/test/fixtures";
import { PreparationWorkflowSteps } from "./PreparationWorkflowSteps";

/* The rail's current chip used to be read straight off the projection's
   `preparation_state`, so an edit that made the backend transiently re-report an earlier
   state moved the rail backward while the reader stayed on the same screen. `stage` - the
   screen actually open - is now the sole source of the current chip; the projection may
   still raise which earlier chips already show a checkmark, but never steals or drops the
   current one. */

const railLabel = (): string => screen.getByLabelText(/שלבי הכנת קורות החיים/).getAttribute("aria-label") ?? "";

describe("PreparationWorkflowSteps", () => {
  it("keeps the open screen's stage current even when the projection reports an earlier one", () => {
    render(
      <MemoryRouter>
        <PreparationWorkflowSteps
          applicationId="app-1"
          detail={detail({ preparation_state: "needs_review" })}
          stage="draft"
        />
      </MemoryRouter>,
    );

    expect(railLabel()).toContain("שלב 3 מתוך 4");
  });

  it("keeps the open screen's stage current even when the projection reports a later one", () => {
    render(
      <MemoryRouter>
        <PreparationWorkflowSteps
          applicationId="app-1"
          detail={detail({ preparation_state: "draft_in_progress" })}
          stage="analysis"
        />
      </MemoryRouter>,
    );

    expect(railLabel()).toContain("שלב 2 מתוך 4");
  });

  it("marks the ready stage complete rather than current once its own screen is open", () => {
    render(
      <MemoryRouter>
        <PreparationWorkflowSteps applicationId="app-1" detail={detail({ preparation_state: "ready" })} stage="ready" />
      </MemoryRouter>,
    );

    expect(railLabel()).toContain("הושלם, 4 מתוך 4");
  });
});
